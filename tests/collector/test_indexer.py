from pathlib import Path
from typing import Union
from unittest.mock import patch

import pytest
from questionpy_common.manifest import Manifest

from questionpy_server import WorkerPool
from questionpy_server.collector.abc import BaseCollector
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from tests.conftest import PACKAGES


@pytest.mark.parametrize('kind', [PACKAGES[0].path, PACKAGES[0].manifest])
@patch('questionpy_server.collector.lms_collector.LMSCollector', spec=LMSCollector)
async def test_register_package_with_path_and_manifest(collector: LMSCollector, kind: Union[Path, Manifest]) -> None:
    indexer = Indexer(WorkerPool(0, 0))
    await indexer.register_package(PACKAGES[0].hash, kind, collector)

    # Package is accessible by hash.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is not None
    assert package.hash == PACKAGES[0].hash
    assert package.manifest == PACKAGES[0].manifest


@patch('questionpy_server.collector.lms_collector.LMSCollector', spec=LMSCollector)
async def test_register_package_from_lms(collector: LMSCollector) -> None:
    indexer = Indexer(WorkerPool(0, 0))
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, collector)

    # Package is not accessible by name and version.
    package = indexer.get_by_name_and_version(PACKAGES[0].manifest.short_name, PACKAGES[0].manifest.version)
    assert package is None

    # Package is not accessible by name.
    packages_by_name = indexer.get_by_name(PACKAGES[0].manifest.short_name)
    assert len(packages_by_name) == 0

    # Package is not accessible by retrieving all packages.
    packages = indexer.get_packages()
    assert len(packages) == 0


@pytest.mark.parametrize('collector', [LocalCollector, RepoCollector])
async def test_register_package_from_local_and_repo_collector(collector: BaseCollector) -> None:
    # Create mock.
    collector = patch(collector.__module__, spec=collector).start()

    indexer = Indexer(WorkerPool(0, 0))
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, collector)

    # Package is accessible by hash.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is not None
    assert package.hash == PACKAGES[0].hash
    assert package.manifest == PACKAGES[0].manifest

    # Package is accessible by name and version.
    new_package = indexer.get_by_name_and_version(PACKAGES[0].manifest.short_name, PACKAGES[0].manifest.version)
    assert new_package is not None
    assert new_package is package

    # Package is accessible by name.
    packages_by_name = indexer.get_by_name(PACKAGES[0].manifest.short_name)
    assert len(packages_by_name) == 1
    assert packages_by_name[package.manifest.version] is package

    # Package is accessible by retrieving all packages.
    packages = indexer.get_packages()
    assert len(packages) == 1
    assert next(iter(packages)) is package


async def test_register_package_with_same_hash_as_existing_package() -> None:
    indexer = Indexer(WorkerPool(0, 0))

    # Register package from local collector.
    local_collector = patch(LocalCollector.__module__, spec=LocalCollector).start()
    package = await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, local_collector)

    # Register package from repo collector.
    repo_collector = patch(RepoCollector.__module__, spec=RepoCollector).start()
    package_2 = await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, repo_collector)
    assert package is package_2

    # Register package from LMS collector.
    with patch('questionpy_server.package.PackageSources.add') as add:
        lms_collector = patch(LMSCollector.__module__, spec=LMSCollector).start()
        package_3 = await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].path, lms_collector)
        assert package is package_3

        # Source gets added to package.
        add.assert_called_once_with(lms_collector)

    # Package will only be listed once.
    packages_by_name = indexer.get_by_name(PACKAGES[0].manifest.short_name)
    assert len(packages_by_name) == 1
    assert packages_by_name[package.manifest.version] is package

    packages = indexer.get_packages()
    assert len(packages) == 1
    assert next(iter(packages)) is package


@pytest.mark.skip(reason='Not implemented yet.')
async def test_register_package_with_same_name_and_version_as_existing_package() -> None:
    pass


@pytest.mark.skip(reason='Not implemented yet.')
async def test_register_package_with_same_name_and_version_as_existing_package_but_different_hash() -> None:
    pass


async def test_unregister_package_with_lms_source() -> None:
    indexer = Indexer(WorkerPool(0, 0))
    collector = patch(LMSCollector.__module__, spec=LMSCollector).start()
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, collector)

    indexer.unregister_package(PACKAGES[0].hash, collector)

    # Package is not accessible after unregistering.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is None


@pytest.mark.parametrize('collector', [LocalCollector, RepoCollector])
async def test_unregister_package_with_local_and_repo_source(collector: BaseCollector) -> None:
    indexer = Indexer(WorkerPool(0, 0))
    collector = patch(collector.__module__, spec=collector).start()
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, collector)

    indexer.unregister_package(PACKAGES[0].hash, collector)

    # Package is not accessible after unregistering.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is None

    # Package is not accessible by name and version.
    package = indexer.get_by_name_and_version(PACKAGES[0].manifest.short_name, PACKAGES[0].manifest.version)
    assert package is None

    # Package is not accessible by name.
    packages = indexer.get_by_name(PACKAGES[0].manifest.short_name)
    assert len(packages) == 0


async def test_unregister_package_with_multiple_sources() -> None:
    indexer = Indexer(WorkerPool(0, 0))

    # Register package from local, repo, and LMS collector.
    lms_collector = patch(LMSCollector.__module__, spec=LMSCollector).start()
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, lms_collector)

    local_collector = patch(LocalCollector.__module__, spec=LocalCollector).start()
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, local_collector)

    repo_collector = patch(RepoCollector.__module__, spec=RepoCollector).start()
    await indexer.register_package(PACKAGES[0].hash, PACKAGES[0].manifest, repo_collector)

    # Unregister package from local collector.
    indexer.unregister_package(PACKAGES[0].hash, local_collector)

    # Package is still accessible by hash.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is not None

    # Package is still accessible by name and version.
    package = indexer.get_by_name_and_version(PACKAGES[0].manifest.short_name, PACKAGES[0].manifest.version)
    assert package is not None

    # Package is still accessible by name.
    packages = indexer.get_by_name(PACKAGES[0].manifest.short_name)
    assert len(packages) == 1

    # Unregister package from repo collector.
    indexer.unregister_package(PACKAGES[0].hash, repo_collector)

    # Package is still accessible by hash.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is not None

    # Package is not accessible by name and version.
    package = indexer.get_by_name_and_version(PACKAGES[0].manifest.short_name, PACKAGES[0].manifest.version)
    assert package is None

    # Package is not accessible by name.
    packages = indexer.get_by_name(PACKAGES[0].manifest.short_name)
    assert len(packages) == 0

    # Unregister package from LMS collector.
    indexer.unregister_package(PACKAGES[0].hash, lms_collector)

    # Package is not accessible by hash.
    package = indexer.get_by_hash(PACKAGES[0].hash)
    assert package is None
