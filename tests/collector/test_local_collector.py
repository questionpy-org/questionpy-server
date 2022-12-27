from pathlib import Path
from shutil import copy

import pytest
from _pytest.tmpdir import TempPathFactory

from watchdog.events import (FileCreatedEvent, FileDeletedEvent, FileMovedEvent, FileModifiedEvent)  # type: ignore

from questionpy_server.package import Package
from questionpy_server.worker.controller import WorkerPool
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.local_collector import LocalCollector
from tests.conftest import PACKAGES, get_file_hash


def create_local_collector(tmp_path_factory: TempPathFactory) -> tuple[LocalCollector, Path]:
    """
    Create a local collector and return it and the directory it is using.

    :param tmp_path_factory: Factory for temporary directories.
    :return: Local collector and directory.
    """

    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(0, 0))
    return LocalCollector(path, indexer), path


async def test_ignore_files_with_wrong_extension(tmp_path_factory: TempPathFactory) -> None:
    # File exists before initializing.
    directory = tmp_path_factory.mktemp('qpy')
    ignore_file = directory / 'wrong.extension'
    ignore_file.touch()

    indexer = Indexer(WorkerPool(0, 0))
    local_collector = LocalCollector(directory, indexer)

    async with local_collector:
        assert len(local_collector.map.paths) == 0

    # File gets created after initialization.
    local_collector, directory = create_local_collector(tmp_path_factory)
    async with local_collector:
        ignore_file = directory / 'wrong.extension'
        ignore_file.touch()
        assert len(local_collector.map.paths) == 0


async def test_package_exists_before_init(tmp_path_factory: TempPathFactory) -> None:
    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(0, 0))
    local_collector = LocalCollector(path, indexer)

    package_path = copy(PACKAGES[0].path, path)
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)

    async with local_collector:
        # Check if the package exists.
        actual_package_path = await local_collector.get_path(package)
        assert actual_package_path.is_file()
        assert str(actual_package_path) == package_path
        assert get_file_hash(actual_package_path) == package.hash


@pytest.mark.skip(reason='Not working yet.')
async def test_package_gets_created(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    async with local_collector:
        # Create a package in the directory.
        package_path = copy(PACKAGES[0].path, directory)
        package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)

        local_collector._event_handler.dispatch(FileCreatedEvent(package_path))

        path = await local_collector.get_path(package)
        assert path == Path(package_path)


@pytest.mark.skip(reason='Not working yet.')
async def test_package_gets_modified(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    package_path = copy(PACKAGES[0].path, directory)
    package_1 = Package(PACKAGES[0].hash, PACKAGES[0].manifest)
    package_2 = Package(PACKAGES[1].hash, PACKAGES[1].manifest)

    async with local_collector:
        # Modify the package and dispatch the event.
        Path(package_path).write_bytes(PACKAGES[1].path.read_bytes())
        local_collector._event_handler.dispatch(FileModifiedEvent(package_path))

        with pytest.raises(FileNotFoundError):
            await local_collector.get_path(package_1)

        assert Path(package_path) == await local_collector.get_path(package_2)


@pytest.mark.skip(reason='Not working yet.')
async def test_package_gets_deleted(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    package_path = copy(PACKAGES[0].path, directory)
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)

    async with local_collector:
        # Remove package from the directory and dispatch the event.
        Path(package_path).unlink()
        local_collector._event_handler.dispatch(FileDeletedEvent(package_path))

        with pytest.raises(FileNotFoundError):
            await local_collector.get_path(package)


@pytest.mark.skip(reason='Not working yet.')
async def test_package_gets_moved_from_package_to_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = copy(PACKAGES[0].path, directory)
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)

    async with local_collector:
        # Rename the package and dispatch the event.
        dest_path = src_path + '.qpy'
        Path(src_path).rename(dest_path)
        local_collector._event_handler.dispatch(FileMovedEvent(src_path, dest_path))

        assert Path(dest_path) == await local_collector.get_path(package)


@pytest.mark.skip(reason='Not working yet.')
async def test_package_gets_moved_from_non_package_to_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = copy(PACKAGES[0].path, directory / 'non.package')
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)

    async with local_collector:
        # Rename the package and dispatch the event.
        dest_path = src_path.with_suffix('.qpy')
        src_path.rename(dest_path)
        local_collector._event_handler.dispatch(FileMovedEvent(str(src_path), str(dest_path)))

        assert dest_path == await local_collector.get_path(package)


@pytest.mark.skip(reason='Not working yet.')
async def test_package_gets_moved_from_package_to_non_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = copy(PACKAGES[0].path, directory)
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)

    async with local_collector:
        # Rename the package and dispatch the event (valid packages need the file extension '.qpy').
        dest_path = src_path + '.new'
        Path(src_path).rename(dest_path)
        local_collector._event_handler.dispatch(FileMovedEvent(src_path, dest_path))

        with pytest.raises(FileNotFoundError):
            await local_collector.get_path(package)
