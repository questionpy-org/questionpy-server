import logging
from asyncio import run_coroutine_threadsafe, AbstractEventLoop, get_event_loop, to_thread
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


class LocalCollectorEventHandler(PatternMatchingEventHandler):
    """
    Handles events for the local collector.
    """

    def __init__(self, local_collector: 'LocalCollector', loop: AbstractEventLoop) -> None:
        super().__init__(patterns=['*.qpy'], ignore_directories=True, case_sensitive=True)

        self._local_collector = local_collector
        self._loop = loop
        self._log = logging.getLogger('questionpy-server')

    def _push_package(self, path_str: str) -> None:
        path = Path(path_str).resolve()

        if path.suffix != '.qpy':
            return

        package_hash = calculate_hash(path)
        self._local_collector.map.insert(package_hash, path)

        run_coroutine_threadsafe(
            self._local_collector.indexer.register_package(package_hash, path, self._local_collector),
            self._loop
        ).result()

    def _pop_package(self, path_str: str) -> None:
        path = Path(path_str).resolve()
        package_hash = self._local_collector.map.pop(path)
        if package_hash:
            packages = self._local_collector.map.get(package_hash)
            if packages is None or len(packages) == 0:
                self._local_collector.indexer.unregister_package(package_hash, self._local_collector)

    def on_created(self, event: FileCreatedEvent) -> None:
        self._push_package(event.src_path)
        self._log.info("Package %s was created.", event.src_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        self._pop_package(event.src_path)
        self._log.info("Package %s was deleted.", event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        dest_path = Path(event.dest_path)
        if dest_path.suffix != '.qpy':
            # Package was moved to a non-package file.
            self._pop_package(event.src_path)
            self._log.info("Package %s was moved to %s and is therefore unregistered.", event.src_path, event.dest_path)
            return

        src_path = Path(event.src_path)
        if src_path.suffix != '.qpy':
            # Package was moved from a non-package file.
            self._push_package(event.dest_path)
            self._log.info("Package %s was moved to %s and is therefore registered.", event.src_path, event.dest_path)
            return

        if package_hash := self._local_collector.map.pop(src_path):
            self._local_collector.map.insert(package_hash, dest_path)
            self._log.info("Package %s was moved to %s.", event.src_path, event.dest_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        self._pop_package(event.src_path)
        self._push_package(event.src_path)
        self._log.info("Package %s was modified.", event.src_path)


class LocalCollector(BaseCollector):
    """
    Handles packages located in a local directory.
    """

    directory: Path

    map: PathToHash

    _observer: Observer

    def __init__(self, directory: Path, indexer: 'Indexer'):
        super().__init__(indexer)

        self.directory = directory
        self.map = PathToHash()

    async def start(self) -> None:
        # Populate the map.
        for file in self.directory.iterdir():
            if file.suffix == '.qpy':
                file = file.resolve()
                package_hash = await to_thread(calculate_hash, file)
                self.map.insert(package_hash, file)
                await self.indexer.register_package(package_hash, file, self)

        # Start the directory observer.
        event_handler = LocalCollectorEventHandler(self, get_event_loop())
        self._observer = Observer()
        self._observer.schedule(event_handler, str(self.directory))
        self._observer.start()

        log = logging.getLogger('questionpy-server')
        log.info("LocalCollector started for directory %s with %s unique package(s).", self.directory,
                 len(self.map.hashes))

    async def stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    async def get_path(self, package: 'Package') -> Path:
        files = self.map.get(package.hash)

        if files is not None:
            for file in files:
                if file.exists():
                    return file
                self.map.pop(package.hash)

        raise FileNotFoundError
