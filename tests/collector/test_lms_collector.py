import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.web import HashContainer
from tests.conftest import PACKAGES


def create_lms_collector(tmp_path_factory: TempPathFactory) -> tuple[LMSCollector, FileLimitLRU]:
    """
    Create a local collector and return it and the cache it is using.

    :param tmp_path_factory: Factory for temporary directories.
    :return: Local collector and cache.
    """

    path = tmp_path_factory.mktemp('qpy')
    cache = FileLimitLRU(path, 20 * 1024 * 1024)
    indexer = Indexer(WorkerPool(0, 0))
    return LMSCollector(cache, indexer), cache


async def test_put(tmp_path_factory: TempPathFactory) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory)

    package_bytes = PACKAGES[0].path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGES[0].hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Check if package is stored in cache.
    cache_path = cache.get(PACKAGES[0].hash)
    lms_path = await lms_collector.get_path(package)
    assert cache_path == lms_path

    # Put package again.
    package_2 = await lms_collector.put(hash_container)
    assert package_2 is package


async def test_get_non_existing_file(tmp_path_factory: TempPathFactory) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory)

    package_bytes = PACKAGES[0].path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGES[0].hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Remove package from cache.
    await cache.remove(PACKAGES[0].hash)

    with pytest.raises(FileNotFoundError):
        await lms_collector.get_path(package)
