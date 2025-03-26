#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from unittest.mock import patch

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_common.constants import KiB
from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.hash import HashContainer, calculate_hash
from questionpy_server.package import Package
from questionpy_server.worker.runtime.messages import BaseWorkerError
from tests.conftest import PACKAGE


def create_lms_collector(
    tmp_path_factory: TempPathFactory, worker_pool: WorkerPool
) -> tuple[LMSCollector, FileLimitLRU]:
    """Creates and returns a local collector along with the cache it is using."""
    path = tmp_path_factory.mktemp("qpy")
    cache = FileLimitLRU(path, 100 * KiB, extension=".qpy")
    indexer = Indexer(worker_pool)
    return LMSCollector(cache, indexer), cache


async def test_package_in_cache_before_init(tmp_path_factory: TempPathFactory) -> None:
    cache = FileLimitLRU(tmp_path_factory.mktemp("qpy"), 100 * KiB, extension=".qpy")

    # Put package into cache.
    await cache.put(PACKAGE.hash, PACKAGE.path.read_bytes())

    # Create and start collector.
    with patch(Indexer.__module__, spec=Indexer) as indexer:
        lms_collector = LMSCollector(cache, indexer)
        await lms_collector.start()

        # Check if package gets indexed.
        indexer.register_package.assert_called_once()

    # Check if package is registered.
    package = Package(PACKAGE.hash, PACKAGE.manifest)
    path = await lms_collector.get_path(package)

    assert path is not None


async def test_put(tmp_path_factory: TempPathFactory, worker_pool: WorkerPool) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory, worker_pool)

    package_bytes = PACKAGE.path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGE.hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Check if package is stored in cache.
    cache_path = cache.get(PACKAGE.hash)
    lms_path = await lms_collector.get_path(package)
    assert cache_path == lms_path

    # Put package again.
    package_2 = await lms_collector.put(hash_container)
    assert package_2 is package


async def test_get_non_existing_file(tmp_path_factory: TempPathFactory, worker_pool: WorkerPool) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory, worker_pool)

    package_bytes = PACKAGE.path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGE.hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Remove package from cache.
    await cache.remove(PACKAGE.hash)

    with pytest.raises(FileNotFoundError):
        await lms_collector.get_path(package)


async def test_lms_collector_is_resilient_to_faulty_packages_on_start(
    tmp_path_factory: TempPathFactory, worker_pool: WorkerPool
) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory, worker_pool)

    invalid_package = b"this is a invalid package"
    file = cache.directory / f"{calculate_hash(invalid_package)}.qpy"
    file.write_bytes(invalid_package)

    valid_package = PACKAGE.path.read_bytes()
    hash_container = HashContainer(valid_package, PACKAGE.hash)

    async with lms_collector:
        # The corrupt package should be removed from the cache.
        assert not cache.contains(hash_container.hash)

        # Valid packages can still be registered.
        package = await lms_collector.put(hash_container)
        assert cache.get(hash_container.hash) == await lms_collector.get_path(package)


async def test_lms_collector_raises_error_on_faulty_package_on_put(
    tmp_path_factory: TempPathFactory, worker_pool: WorkerPool
) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory, worker_pool)

    invalid_package = b"this is a invalid package"
    hash_container = HashContainer(invalid_package, calculate_hash(invalid_package))

    with pytest.raises(BaseWorkerError):
        await lms_collector.put(hash_container)

    # The corrupt package should be removed from the cache.
    assert not cache.contains(hash_container.hash)
