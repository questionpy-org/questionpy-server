from asyncio import run
from pathlib import Path
from typing import TYPE_CHECKING, Optional, overload, Union

from watchdog.observers import Observer  # type: ignore
from watchdog.events import (PatternMatchingEventHandler, FileCreatedEvent, FileDeletedEvent,  # type: ignore
                             FileMovedEvent, FileModifiedEvent)  # type: ignore

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
        self._map: dict[Path, str] = {}
        # Maps a hash to the paths.
        self._map_inv: dict[str, set[Path]] = {}

    def insert(self, package_hash: str, path: Path) -> None:
        """
        Inserts a package hash and its path into the map.

        :param package_hash: The package hash.
        :param path: The path.
        """

        self._map[path] = package_hash
        self._map_inv.setdefault(package_hash, set()).add(path.resolve())

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
            return self._map.get(key)

        if isinstance(key, str):
            return self._map_inv.get(key)

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
            package_hash = self._map.pop(key, None)
            if not package_hash:
                return None

            # Remove the path from the inverse map.
            self._map_inv[package_hash].discard(key)

            # If no paths are left, remove the hash from the map.
            if not self._map_inv[package_hash]:
                self._map_inv.pop(package_hash)

            return package_hash

        if isinstance(key, str):
            paths = self._map_inv.pop(key, None)
            if paths:
                for path in paths:
                    self._map.pop(path)
            return paths

        raise TypeError(f'Expected Path or str, got {type(key)}')


class LocalCollectorEventHandler(PatternMatchingEventHandler):
    """
    Handles events for the local collector.
    """

    def __init__(self, local_collector: 'LocalCollector'):
        super().__init__(patterns=['*.qpy'], ignore_directories=True, case_sensitive=True)
        self._local_collector = local_collector

    async def _push_package_async(self, path_str: str) -> None:
        path = Path(path_str).resolve()

        if path.suffix != '.qpy':
            return

        package_hash = calculate_hash(path)
        self._local_collector.map.insert(package_hash, path)
        await self._local_collector.indexer.register_package(package_hash, path, self._local_collector)

    def _push_package(self, path_str: str) -> None:
        run(self._push_package_async(path_str))

    def _pop_package(self, path_str: str) -> None:
        path = Path(path_str).resolve()
        package_hash = self._local_collector.map.pop(path)
        if package_hash:
            packages = self._local_collector.map.get(package_hash)
            if packages is None or len(packages) == 0:
                self._local_collector.indexer.unregister_package(package_hash, self._local_collector)

    def on_created(self, event: FileCreatedEvent) -> None:
        self._push_package(event.src_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        self._pop_package(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        dest_path = Path(event.dest_path)
        if dest_path.suffix != '.qpy':
            # Package was moved to a non-package file.
            self._pop_package(event.src_path)
            return

        src_path = Path(event.src_path)
        if src_path.suffix != '.qpy':
            # Package was moved from a non-package file.
            self._push_package(event.dest_path)
            return

        if package_hash := self._local_collector.map.pop(src_path):
            self._local_collector.map.insert(package_hash, dest_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        self._pop_package(event.src_path)
        self._push_package(event.src_path)


class LocalCollector(BaseCollector):
    """
    Handles packages located in a local directory.
    """

    directory: Path
    indexer: 'Indexer'

    map: PathToHash

    def __init__(self, directory: Path, indexer: 'Indexer'):
        self.directory = directory
        self.indexer = indexer

        self.map = PathToHash()

        for file in self.directory.iterdir():
            if file.suffix == '.qpy':
                file = file.resolve()
                package_hash = calculate_hash(file)
                self.map.insert(package_hash, file)
                run(self.indexer.register_package(package_hash, file, self))

        event_handler = LocalCollectorEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(directory))
        self.observer.start()

    def get_path_by_hash(self, package_hash: str) -> Path:
        files = self.map.get(package_hash)

        if files is not None:
            for file in files:
                if file.exists():
                    return file
                self.map.pop(package_hash)

        raise FileNotFoundError

    async def get_path(self, package: 'Package') -> Path:
        return self.get_path_by_hash(package.hash)
