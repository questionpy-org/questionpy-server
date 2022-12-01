from unittest.mock import patch, Mock

from _pytest.tmpdir import TempPathFactory

from questionpy_server import WorkerPool
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.collector import LocalCollector
from questionpy_server.package import Package
from tests.conftest import PACKAGES


async def test_update_gets_called_on_each_get_call(tmp_path_factory: TempPathFactory) -> None:
    indexer = Indexer([])

    with patch.object(indexer, 'update') as update:
        await indexer.get_packages()
        assert update.call_count == 1

        await indexer.get_by_name('test')
        assert update.call_count == 2

        await indexer.get_by_name_and_version('test', '1.0.0')
        assert update.call_count == 3

        await indexer.get_by_hash('test')
        assert update.call_count == 4


async def test_update_calls_get_packages(tmp_path_factory: TempPathFactory) -> None:
    # Create local collector.
    local_directory = tmp_path_factory.mktemp('qpy')
    local_collector = LocalCollector(local_directory, WorkerPool(0, 0))

    # Create indexer.
    indexer = Indexer([local_collector])

    # Check if update calls get_packages.
    with patch.object(local_collector, 'get_packages') as get_packages:
        await indexer.update(force=True)
        get_packages.assert_called_once()


def test_register_packages() -> None:
    # The method register_packages should call register_package for each package.
    packages = [Mock() for _ in range(3)]
    indexer = Indexer([])
    with patch.object(indexer, 'register_package') as register_package:
        indexer.register_packages(packages)
        assert register_package.call_count == 3


async def test_local_or_repo_packages(tmp_path_factory: TempPathFactory) -> None:
    # Create indexer.
    indexer = Indexer([])
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest, Mock(), PACKAGES[0].path)

    # Register package.
    indexer.register_package(package, from_lms=False)

    # Update removes package if it is not found in the collector.
    await indexer.update(force=True)
    indexed_package = await indexer.get_by_hash(package.hash)
    assert indexed_package is None

    # Register package again.
    indexer.register_package(package, from_lms=False)

    # Make update do nothing.
    with patch.object(indexer, 'update'):
        # Package is accessible by hash.
        indexed_package = await indexer.get_by_hash(package.hash)
        assert indexed_package == package

        # Package is accessible by name.
        indexed_packages_dict = await indexer.get_by_name(package.manifest.short_name)
        assert len(indexed_packages_dict) == 1
        assert indexed_packages_dict[package.manifest.version] == package

        # Package is accessible by name and version.
        indexed_package = await indexer.get_by_name_and_version(package.manifest.short_name, package.manifest.version)
        assert indexed_package == package

        # Package will be listed in get_packages.
        indexed_packages_set = await indexer.get_packages()
        assert len(indexed_packages_set) == 1
        assert package in indexed_packages_set

    # Unregister package.
    indexer.unregister_package(package.hash)
    indexed_package = await indexer.get_by_hash(package.hash)
    assert indexed_package is None


async def test_lms_packages(tmp_path_factory: TempPathFactory) -> None:
    # Create indexer.
    indexer = Indexer([])
    package = Package(PACKAGES[0].hash, PACKAGES[0].manifest, Mock(), PACKAGES[0].path)

    # Register LMS Package.
    indexer.register_package(package, from_lms=True)

    # Package is accessible by hash.
    indexed_package = await indexer.get_by_hash(package.hash)
    assert indexed_package is package

    # Package is not accessible by name.
    indexed_packages_dict = await indexer.get_by_name(package.manifest.short_name)
    assert len(indexed_packages_dict) == 0

    # Package is not accessible by name and version.
    indexed_package = await indexer.get_by_name_and_version(package.manifest.short_name, package.manifest.version)
    assert indexed_package is None

    # Package will not be listed in get_packages.
    indexed_packages_set = await indexer.get_packages()
    assert len(indexed_packages_set) == 0

    # Package does not get deleted on update.
    await indexer.update(force=True)
    indexed_package = await indexer.get_by_hash(package.hash)
    assert indexed_package is package

    # Package can be unregistered.
    indexer.unregister_package(package.hash)
    indexed_package = await indexer.get_by_hash(package.hash)
    assert indexed_package is None
