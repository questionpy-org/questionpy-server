from shutil import copy

import pytest
from _pytest.tmpdir import TempPathFactory

from tests.conftest import PACKAGES, get_file_hash

from questionpy_server import WorkerPool
from questionpy_server.collector.collector import LocalCollector


async def test_ignore_files_with_wrong_extension(tmp_path_factory: TempPathFactory) -> None:
    directory = tmp_path_factory.mktemp('qpy')
    (directory / 'wrong.extension').touch()
    local_collector = LocalCollector(directory, WorkerPool(0, 0))
    packages = await local_collector.get_packages()
    assert len(packages) == 0


async def test_package_exists_before_init(tmp_path_factory: TempPathFactory) -> None:
    # Initialize local collector on directory with existing package.
    directory = tmp_path_factory.mktemp('qpy')
    package_path = directory / PACKAGES[0].path.name

    copy(PACKAGES[0].path, package_path)
    local_collector = LocalCollector(directory, WorkerPool(0, 0))

    # Check if the package exists.
    actual_package_path = local_collector.get_path_by_hash(PACKAGES[0].hash)
    assert actual_package_path.is_file()
    assert actual_package_path == package_path
    assert get_file_hash(package_path) == PACKAGES[0].hash

    # Check if the package is in the list of packages.
    packages = await local_collector.get_packages()
    assert len(packages) == 1
    package = packages.pop()
    assert package.hash == PACKAGES[0].hash

    # Check if path can be found.
    assert await package.get_path() == package_path
    assert await local_collector.get_path(package) == package_path

    # Delete file.
    actual_package_path.unlink()
    with pytest.raises(FileNotFoundError):
        local_collector.get_path_by_hash(package.hash)

    packages = await local_collector.get_packages()
    assert len(packages) == 0


async def test_package_exists_after_init(tmp_path_factory: TempPathFactory) -> None:
    # Create local collector and then copy/add package into directory.
    directory = tmp_path_factory.mktemp('qpy')
    package_path = directory / PACKAGES[0].path.name

    local_collector = LocalCollector(directory, WorkerPool(0, 0))
    copy(PACKAGES[0].path, package_path)

    with pytest.raises(FileNotFoundError):
        # TODO: This should not raise an error.
        local_collector.get_path_by_hash(PACKAGES[0].hash)

    packages = await local_collector.get_packages()
    assert len(packages) == 1
    package = packages.pop()
    assert package.hash == PACKAGES[0].hash

    assert local_collector.get_path_by_hash(PACKAGES[0].hash) == package_path

