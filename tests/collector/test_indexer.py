#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from pathlib import Path
from typing import Union
from unittest.mock import patch

import pytest

from questionpy_common.constants import MiB

from questionpy_server import WorkerPool
from questionpy_server.collector.abc import BaseCollector
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.package import PackageSources
from questionpy_server.utils.manifest import ComparableManifest
from tests.conftest import PACKAGE


@pytest.mark.parametrize("kind", [PACKAGE.path, PACKAGE.manifest])
@patch("questionpy_server.collector.lms_collector.LMSCollector", spec=LMSCollector)
async def test_register_package_with_path_and_manifest(
    collector: LMSCollector, kind: Union[Path, ComparableManifest]
) -> None:
    indexer = Indexer(WorkerPool(1, 200 * MiB))
    await indexer.register_package(PACKAGE.hash, kind, collector)

    # Package is accessible by hash.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is not None
    assert package.hash == PACKAGE.hash
    assert package.manifest == PACKAGE.manifest


@patch("questionpy_server.collector.lms_collector.LMSCollector", spec=LMSCollector)
async def test_register_package_from_lms(collector: LMSCollector) -> None:
    indexer = Indexer(WorkerPool(1, 200 * MiB))
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, collector)

    # Package is not accessible by identifier and version.
    package = indexer.get_by_identifier_and_version(PACKAGE.manifest.identifier, PACKAGE.manifest.version)
    assert package is None

    # Package is not accessible by identifier.
    packages_by_identifier = indexer.get_by_identifier(PACKAGE.manifest.identifier)
    assert len(packages_by_identifier) == 0

    # Package is not accessible by retrieving all packages.
    packages = indexer.get_packages()
    assert len(packages) == 0


@pytest.mark.parametrize("collector", [LocalCollector, RepoCollector])
async def test_register_package_from_local_and_repo_collector(collector: BaseCollector) -> None:
    # Create mock.
    collector = patch(collector.__module__, spec=collector).start()

    indexer = Indexer(WorkerPool(1, 200 * MiB))
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, collector)

    # Package is accessible by hash.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is not None
    assert package.hash == PACKAGE.hash
    assert package.manifest == PACKAGE.manifest

    # Package is accessible by identifier and version.
    new_package = indexer.get_by_identifier_and_version(PACKAGE.manifest.identifier, PACKAGE.manifest.version)
    assert new_package is not None
    assert new_package is package

    # Package is accessible by identifier.
    packages_by_identifier = indexer.get_by_identifier(PACKAGE.manifest.identifier)
    assert len(packages_by_identifier) == 1
    assert packages_by_identifier[package.manifest.version] is package

    # Package is accessible by retrieving all packages.
    packages = indexer.get_packages()
    assert len(packages) == 1
    assert next(iter(packages)) is package


async def test_register_package_with_same_hash_as_existing_package() -> None:
    indexer = Indexer(WorkerPool(1, 200 * MiB))

    # Register package from local collector.
    local_collector = patch(LocalCollector.__module__, spec=LocalCollector).start()
    package = await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, local_collector)

    # Register package from repo collector.
    repo_collector = patch(RepoCollector.__module__, spec=RepoCollector).start()
    package_2 = await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, repo_collector)
    assert package is package_2

    # Register package from LMS collector.
    with patch.object(PackageSources, "add") as add:
        lms_collector = patch(LMSCollector.__module__, spec=LMSCollector).start()
        package_3 = await indexer.register_package(PACKAGE.hash, PACKAGE.path, lms_collector)
        assert package is package_3

        # Source gets added to package.
        add.assert_called_once_with(lms_collector)

    # Package will only be listed once.
    packages_by_identifier = indexer.get_by_identifier(PACKAGE.manifest.identifier)
    assert len(packages_by_identifier) == 1
    assert packages_by_identifier[package.manifest.version] is package

    packages = indexer.get_packages()
    assert len(packages) == 1
    assert next(iter(packages)) is package


async def test_register_two_packages_with_same_manifest_but_different_hashes(caplog: pytest.LogCaptureFixture) -> None:
    # Create mock.
    collector = patch(LocalCollector.__module__, spec=LocalCollector).start()

    # Register a package.
    indexer = Indexer(WorkerPool(1, 200 * MiB))
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, collector)

    with caplog.at_level(logging.WARNING):
        # Register same package with different hash and same manifest.
        await indexer.register_package("different_hash", PACKAGE.manifest, collector)

    message = (
        f"The package {PACKAGE.manifest.identifier} ({PACKAGE.manifest.version}) with hash: "
        f"different_hash already exists with a different hash: {PACKAGE.hash}."
    )
    assert caplog.record_tuples == [("questionpy-server:indexer", logging.WARNING, message)]


async def test_unregister_package_with_lms_source() -> None:
    indexer = Indexer(WorkerPool(1, 200 * MiB))
    collector = patch(LMSCollector.__module__, spec=LMSCollector).start()
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, collector)

    await indexer.unregister_package(PACKAGE.hash, collector)

    # Package is not accessible after unregistering.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is None


@pytest.mark.parametrize("collector", [LocalCollector, RepoCollector])
async def test_unregister_package_with_local_and_repo_source(collector: BaseCollector) -> None:
    indexer = Indexer(WorkerPool(1, 200 * MiB))
    collector = patch(collector.__module__, spec=collector).start()
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, collector)

    await indexer.unregister_package(PACKAGE.hash, collector)

    # Package is not accessible after unregistering.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is None

    # Package is not accessible by identifier and version.
    package = indexer.get_by_identifier_and_version(PACKAGE.manifest.identifier, PACKAGE.manifest.version)
    assert package is None

    # Package is not accessible by identifier.
    packages = indexer.get_by_identifier(PACKAGE.manifest.identifier)
    assert len(packages) == 0


async def test_unregister_package_with_multiple_sources() -> None:
    indexer = Indexer(WorkerPool(1, 200 * MiB))

    # Register package from local, repo, and LMS collector.
    lms_collector = patch(LMSCollector.__module__, spec=LMSCollector).start()
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, lms_collector)

    local_collector = patch(LocalCollector.__module__, spec=LocalCollector).start()
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, local_collector)

    repo_collector = patch(RepoCollector.__module__, spec=RepoCollector).start()
    await indexer.register_package(PACKAGE.hash, PACKAGE.manifest, repo_collector)

    # Unregister package from local collector.
    await indexer.unregister_package(PACKAGE.hash, local_collector)

    # Package is still accessible by hash.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is not None

    # Package is still accessible by identifier and version.
    package = indexer.get_by_identifier_and_version(PACKAGE.manifest.identifier, PACKAGE.manifest.version)
    assert package is not None

    # Package is still accessible by identifier.
    packages = indexer.get_by_identifier(PACKAGE.manifest.identifier)
    assert len(packages) == 1

    # Unregister package from repo collector.
    await indexer.unregister_package(PACKAGE.hash, repo_collector)

    # Package is still accessible by hash.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is not None

    # Package is not accessible by identifier and version.
    package = indexer.get_by_identifier_and_version(PACKAGE.manifest.identifier, PACKAGE.manifest.version)
    assert package is None

    # Package is not accessible by identifier.
    packages = indexer.get_by_identifier(PACKAGE.manifest.identifier)
    assert len(packages) == 0

    # Unregister package from LMS collector.
    await indexer.unregister_package(PACKAGE.hash, lms_collector)

    # Package is not accessible by hash.
    package = indexer.get_by_hash(PACKAGE.hash)
    assert package is None
