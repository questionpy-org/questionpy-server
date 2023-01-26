import logging
from asyncio import to_thread, get_running_loop, create_task
from pathlib import Path
from typing import TYPE_CHECKING, Optional, overload, Union, Generator, Any, cast
from signal import SIGUSR1

from watchdog.utils.dirsnapshot import DirectorySnapshot, EmptyDirectorySnapshot, DirectorySnapshotDiff  # type: ignore

from questionpy_server.collector.abc import BaseCollector
from questionpy_server.misc import calculate_hash

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.package import Package


class PathToHash:
    """
    A class that maps paths to hashes.

    Maps package hashes to their file paths. There can be multiple file paths for a single package hash.
    """

    def __init__(self) -> None:
        # Maps a path to its hash.
        self.paths: dict[Path, str] = {}
        # Maps a hash to the paths.
        self.hashes: dict[str, set[Path]] = {}

    def insert(self, package_hash: str, path: Path) -> None:
        """
        Inserts a package hash and its path into the map.

        :param package_hash: The package hash.
        :param path: The path.
        """

        self.paths[path] = package_hash
        self.hashes.setdefault(package_hash, set()).add(path.resolve())

    @overload
    def get(self, key: Path) -> Optional[str]:
        """
        Gets the hash of a package from its path.

        :param key: The path of the package.
        :return: The hash of the package.
        """

    @overload
    def get(self, key: str) -> Optional[set[Path]]:
        """
        Gets the paths of a package from its hash.

        :param key: The hash of the package.
        :return: The paths of the package.
        """

    def get(self, key: Union[str, Path]) -> Union[Optional[set[Path]], Optional[str]]:
        if isinstance(key, Path):
            return self.paths.get(key)

        if isinstance(key, str):
            return self.hashes.get(key)

        raise TypeError(f'Expected Path or str, got {type(key)}')

    @overload
    def pop(self, key: Path) -> Optional[str]:
        """
        Removes the package with the given path and returns its hash.

        :param key: The path of the package.
        :return: The hash of the package.
        """

    @overload
    def pop(self, key: str) -> Optional[set[Path]]:
        """
        Removes all packages with the given hash and returns their paths.

        :param key: The hash of the packages.
        :return: The paths of the packages.
        """

    def pop(self, key: Union[Path, str]) -> Union[Optional[str], Optional[set[Path]]]:
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

        raise TypeError(f'Expected Path or str, got {type(key)}')

    def replace(self, paths: list[tuple[Path, Path]]) -> None:
        """
        Replaces the paths of packages.

        :param paths: An iterator of tuples in the form of (old_path, new_path).
        """

        if not paths:
            return

        # Unpack the paths.
        old_paths, new_paths = zip(*paths)
        old_paths = cast(tuple[Path], old_paths)
        new_paths = cast(tuple[Path], new_paths)

        package_hashes = [self.pop(path) for path in old_paths]
        for path, package_hash in zip(new_paths, package_hashes):
            if package_hash:
                self.insert(package_hash, path)


class LocalCollector(BaseCollector):
    """
    Handles packages located in a local directory.
    """

    def __init__(self, directory: Path, indexer: 'Indexer'):
        super().__init__(indexer)

        self.directory: Path = directory
        self.map: PathToHash = PathToHash()
        self._snapshot: Optional[DirectorySnapshot] = None
        self._log = logging.getLogger('questionpy-server:local-collector')

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

    async def update(self, with_log: bool = True) -> None:
        """
        Reflect changes in the directory to the indexer and internal map.

        :param with_log: Whether to log the changes.
        """

        def directory_iterator(directory: str) -> Generator[Path, Any, None]:
            """
            Iterates over all packages in the directory.
            Used as the custom directory iterator for DirectorySnapshot.

            :param directory: The directory.
            :return: A generator of paths.
            """

            for file in Path(directory).glob('*.qpy'):
                if file.is_file():
                    yield file

        async def add_package(pkg_hash: str, pkg_path: Path) -> None:
            """
            Adds a package to the map and registers it in the indexer.

            :param pkg_hash: The hash of the package.
            :param pkg_path: The path of the package.
            """

            self.map.insert(pkg_hash, pkg_path)
            await self.indexer.register_package(pkg_hash, pkg_path, self)

        async def remove_package(pkg_path: Path) -> None:
            """
            Removes a package from the map and unregisters it from the indexer.

            :param pkg_path: The path of the package.
            """

            pkg_hash = self.map.pop(pkg_path)
            if not pkg_hash:
                return
            packages = self.map.get(pkg_hash)
            if packages is None or len(packages) == 0:
                # There is no other package with the same hash - unregister it.
                await self.indexer.unregister_package(pkg_hash, self)

        # If no snapshot exists, use EmptyDirectorySnapshot to get all files as created.
        old_snapshot = self._snapshot or EmptyDirectorySnapshot()
        new_snapshot = DirectorySnapshot(str(self.directory), recursive=False, listdir=directory_iterator)
        difference = DirectorySnapshotDiff(old_snapshot, new_snapshot)

        for path in difference.files_created:
            package_path = Path(path)
            package_hash = await to_thread(calculate_hash, package_path)
            await add_package(package_hash, package_path)

        for path in difference.files_deleted:
            package_path = Path(path)
            await remove_package(package_path)

        for path in difference.files_modified:
            package_path = Path(path)
            package_hash = await to_thread(calculate_hash, package_path)
            await remove_package(package_path)
            await add_package(package_hash, package_path)

            self._log.warning("Package %s was modified. This will cause unexpected behavior if the package is "
                              "currently read by a worker.", package_path)

        # Replace paths for moved packages.
        paths = list(map(lambda files: (Path(files[0]), Path(files[1])), difference.files_moved))
        self.map.replace(paths)

        # Update the snapshot.
        self._snapshot = new_snapshot

        if with_log:
            self._log.info("Updated packages: %d created, %d deleted, %d modified, %d moved.",
                           len(difference.files_created), len(difference.files_deleted), len(difference.files_modified),
                           len(difference.files_moved))

    async def get_path(self, package: 'Package') -> Path:
        files = self.map.get(package.hash)

        if files is not None:
            for file in files:
                if file.exists():
                    return file
                self.map.pop(package.hash)

        raise FileNotFoundError
