#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from unittest.mock import patch

import pytest
from _pytest.tmpdir import TempPathFactory
from questionpy_common.constants import KiB, MiB

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.package import Package
from questionpy_server.web import HashContainer
from tests.conftest import PACKAGE


def create_lms_collector(tmp_path_factory: TempPathFactory) -> tuple[LMSCollector, FileLimitLRU]:
    """Create a local collector and return it and the cache it is using.

    Args:
        tmp_path_factory (TempPathFactory): Factory for temporary directories.

    Returns:
        Local collector and cache.
    """

    path = tmp_path_factory.mktemp("qpy")
    cache = FileLimitLRU(path, 100 * KiB, extension=".qpy")
    indexer = Indexer(WorkerPool(1, 200 * MiB))
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


async def test_put(tmp_path_factory: TempPathFactory) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory)

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


async def test_get_non_existing_file(tmp_path_factory: TempPathFactory) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory)

    package_bytes = PACKAGE.path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGE.hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Remove package from cache.
    await cache.remove(PACKAGE.hash)

    with pytest.raises(FileNotFoundError):
        await lms_collector.get_path(package)
