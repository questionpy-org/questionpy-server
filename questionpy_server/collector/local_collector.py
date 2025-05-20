#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from asyncio import Lock, create_task, get_running_loop, to_thread
from collections.abc import Generator
from os import DirEntry, scandir
from pathlib import Path
from signal import SIGUSR1
from typing import TYPE_CHECKING, Any, overload

from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff, EmptyDirectorySnapshot

from questionpy_server.collector.abc import BaseCollector
from questionpy_server.hash import calculate_hash
from questionpy_server.worker.runtime.messages import BaseWorkerError

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.package import Package


def ensure_str(path: bytes | str) -> str:
    """Ensure that a path is a string because the watchdog lib might return paths as bytes."""
    if isinstance(path, bytes):
        return path.decode()
    return path


class PathToHash:
    """A class that maps paths to hashes.

    Maps package hashes to their file paths. There can be multiple file paths for a single package hash.
    """

    def __init__(self) -> None:
        # Maps a path to its hash.
        self.paths: dict[Path, str] = {}
        # Maps a hash to the paths.
        self.hashes: dict[str, set[Path]] = {}

    def insert(self, package_hash: str, path: Path) -> None:
        """Inserts a package hash and its path into the map.

        Args:
            package_hash (str): The package hash.
            path (Path): The path.
        """
        self.paths[path] = package_hash
        self.hashes.setdefault(package_hash, set()).add(path.resolve())

    @overload
    def get(self, key: Path) -> str | None: ...

    @overload
    def get(self, key: str) -> set[Path] | None: ...

    def get(self, key: str | Path) -> set[Path] | str | None:
        if isinstance(key, Path):
            return self.paths.get(key)

        if isinstance(key, str):
            if paths := self.hashes.get(key):
                return paths.copy()
            return None

        msg = f"Expected Path or str, got {type(key)}"
        raise TypeError(msg)

    @overload
    def pop(self, key: Path) -> str | None: ...

    @overload
    def pop(self, key: str) -> set[Path] | None: ...

    def pop(self, key: Path | str) -> str | set[Path] | None:
        """Removes package(s) with given path/hash.

        When path is given, remove the package and return hash. When hash is given,
        remove all matching packages and return their paths.

        Args:
            key (Union[Path, str]): The path or hash of the package(s).

        Returns:
            The paths or hash of the package(s).
        """
        if isinstance(key, Path):
            # Get the hash of the package.
            package_hash = self.paths.pop(key, None)
            if not package_hash:
                return None

            # Remove the path from the inverse map.
            self.hashes[package_hash].discard(key)

            # If no paths are left, remove the hash from the map.
            if not self.hashes[package_hash]:
                self.hashes.pop(package_hash)

            return package_hash

        if isinstance(key, str):
            paths = self.hashes.pop(key, None)
            if paths:
                for path in paths:
                    self.paths.pop(path)
            return paths

        msg = f"Expected Path or str, got {type(key)}"
        raise TypeError(msg)


class LocalCollector(BaseCollector):
    """Handles packages located in a local directory."""

    def __init__(self, directory: Path, indexer: "Indexer"):
        super().__init__(indexer)

        self.directory: Path = directory
        self.map: PathToHash = PathToHash()

        self._lock = Lock()
        self._snapshot: DirectorySnapshot | None = None
        self._log = logging.getLogger("questionpy-server:local-collector")

    async def start(self) -> None:
        # Remove possibly outdated snapshot and update.
        self._snapshot = None
        await self.update(with_log=False)

        # Add signal handler for updating the collector.
        get_running_loop().add_signal_handler(SIGUSR1, lambda: create_task(self.update()))

        self._log.info("Started for directory %s with %s unique package(s).", self.directory, len(self.map.hashes))

    async def stop(self) -> None:
        # Remove signal handler.
        get_running_loop().remove_signal_handler(SIGUSR1)

    # TODO: refactor to reduce complexity
    async def update(self, *, with_log: bool = True) -> None:  # noqa: C901
        """Reflects changes in the directory to the indexer and internal map.

        Args:
            with_log (bool): Whether to log the changes.
        """

        def directory_iterator(directory: str | None) -> Generator[DirEntry, Any, None]:
            """Iterate over all packages in the directory.

            Used as the custom directory iterator for DirectorySnapshot.

            Args:
                directory: The directory.

            Returns:
                A generator of directory entries.
            """
            if directory is not None:
                for entry in scandir(directory):
                    if entry.is_file() and entry.name.endswith(".qpy"):
                        yield entry

        async def add_package(pkg_hash: str, pkg_path: Path) -> bool:
            """Adds a package to the map and registers it in the indexer.

            Args:
                pkg_hash (str): The hash of the package.
                pkg_path (Path): The path of the package.
            """
            try:
                await self.indexer.register_package(pkg_hash, pkg_path, self)
                self.map.insert(pkg_hash, pkg_path)
            except BaseWorkerError:
                self._log.warning("'%s' is an invalid package. Skipping.", pkg_path)
                self._log.debug("Following error was thrown.", exc_info=True)
                return False
            return True

        async def remove_package(pkg_path: Path) -> None:
            """Removes a package from the map and unregisters it from the indexer.

            Args:
                pkg_path (Path): The path of the package.
            """
            if not (pkg_hash := self.map.pop(pkg_path)):
                return
            if not (packages := self.map.get(pkg_hash)) or len(packages) == 0:
                # There are no other packages with the same hash - unregister it.
                await self.indexer.unregister_package(pkg_hash, self)

        async with self._lock:
            # If no snapshot exists, use EmptyDirectorySnapshot to get all files as created.
            old_snapshot = self._snapshot or EmptyDirectorySnapshot()
            new_snapshot = await to_thread(
                DirectorySnapshot, str(self.directory), recursive=False, listdir=directory_iterator
            )
            difference = DirectorySnapshotDiff(old_snapshot, new_snapshot)

            corrupt_created_package = 0
            corrupt_modified_package = 0

            for path in difference.files_created:
                package_path = Path(ensure_str(path))
                package_hash = await to_thread(calculate_hash, package_path)
                corrupt_created_package += not await add_package(package_hash, package_path)

            for path in difference.files_deleted:
                package_path = Path(ensure_str(path))
                await remove_package(package_path)

            for path in difference.files_modified:
                package_path = Path(ensure_str(path))
                package_hash = await to_thread(calculate_hash, package_path)
                await remove_package(package_path)
                corrupt_modified_package += not await add_package(package_hash, package_path)

                self._log.warning(
                    "Package %s was modified. This will cause unexpected behavior if the package is "
                    "currently read by a worker.",
                    package_path,
                )

            # We need to remove every old path before inserting new ones to avoid conflicts when paths get swapped.
            entries = []
            for old_path, new_path in difference.files_moved:
                # Remove old path and save the package hash.
                if existing_hash := self.map.pop(Path(ensure_str(old_path))):
                    entries.append((existing_hash, Path(ensure_str(new_path))))
            for entry in entries:
                # Insert package hash with new path.
                self.map.insert(*entry)

            # Update the snapshot.
            self._snapshot = new_snapshot

        if with_log:
            self._log.info(
                "Updated packages: %d created, %d deleted, %d modified, %d moved.",
                len(difference.files_created) - corrupt_created_package,
                len(difference.files_deleted),
                len(difference.files_modified) - corrupt_modified_package,
                len(difference.files_moved),
            )

    async def get_path(self, package: "Package") -> Path:
        files = self.map.get(package.hash)

        if files is not None:
            for file in files:
                if file.exists():
                    return file
                self.map.pop(package.hash)

        raise FileNotFoundError
