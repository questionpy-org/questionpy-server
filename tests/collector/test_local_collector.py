from pathlib import Path
from shutil import copy

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server.package import Package
from questionpy_server.worker.controller import WorkerPool
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.local_collector import LocalCollector
from tests.conftest import PACKAGES, get_file_hash, TestPackage


def create_local_collector(tmp_path_factory: TempPathFactory) -> tuple[LocalCollector, Path]:
    """
    Create a local collector and return it and the directory it is using.

    :param tmp_path_factory: Factory for temporary directories.
    :return: Local collector and directory.
    """

    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(0, 0))
    return LocalCollector(path, indexer), path


def create_local_collector_with_package(tmp_path_factory: TempPathFactory) \
        -> tuple[LocalCollector, Path, TestPackage, Path]:
    """
    Create a local collector with preexisting package.

    :param tmp_path_factory: Factory for temporary directories.
    :return: Local collector, directory, package, and package path.
    """

    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(0, 0))
    local_collector = LocalCollector(path, indexer)

    package_path = copy(PACKAGES[0].path, path)

    return local_collector, path, PACKAGES[0], package_path


async def test_ignore_files_with_wrong_extension(tmp_path_factory: TempPathFactory) -> None:
    # File exists before initializing.
    directory = tmp_path_factory.mktemp('qpy')
    ignore_file = directory / 'wrong.extension'
    ignore_file.touch()
    indexer = Indexer(WorkerPool(0, 0))
    package_hash = LocalCollector(directory, indexer).map.get(ignore_file)
    assert package_hash is None

    # File gets created after initialization.
    local_collector, directory = create_local_collector(tmp_path_factory)
    ignore_file = directory / 'wrong.extension'
    ignore_file.touch()
    package_hash = local_collector.map.get(ignore_file)
    assert package_hash is None


@pytest.mark.skip(reason='Not implemented yet.')
async def test_package_exists_before_init(tmp_path_factory: TempPathFactory) -> None:
    local_collector, _, package, package_path = create_local_collector_with_package(tmp_path_factory)

    # Check if the package exists.
    actual_package_path = await local_collector.get_path(Package(package.hash, package.manifest))
    assert actual_package_path.is_file()
    assert actual_package_path == package_path
    assert get_file_hash(actual_package_path) == package.hash


@pytest.mark.skip(reason='Observer is not working under test conditions.')
async def test_package_gets_created(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)
    await local_collector.start()

    package_path = copy(PACKAGES[0].path, directory)
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest)
    print(package.hash, package_path, directory, local_collector.map.paths, local_collector.map.hashes)

    path = await local_collector.get_path(package)
    assert path == Path(package_path)


@pytest.mark.skip(reason='Not implemented yet.')
async def test_package_gets_modified(tmp_path_factory: TempPathFactory) -> None:
    pass


@pytest.mark.skip(reason='Not implemented yet.')
async def test_package_gets_deleted(tmp_path_factory: TempPathFactory) -> None:
    pass


@pytest.mark.skip(reason='Not implemented yet.')
async def test_package_gets_moved(tmp_path_factory: TempPathFactory) -> None:
    pass
