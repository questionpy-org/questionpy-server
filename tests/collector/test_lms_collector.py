import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.collector import LMSCollector
from questionpy_server.web import HashContainer
from tests.conftest import PACKAGES


def create_lms_collector(tmp_path_factory: TempPathFactory) -> tuple[LMSCollector, FileLimitLRU]:
    path = tmp_path_factory.mktemp('qpy')
    cache = FileLimitLRU(path, 20 * 1024 * 1024)
    return LMSCollector(cache, WorkerPool(0, 0)), cache


async def test_put(tmp_path_factory: TempPathFactory) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory)

    package_bytes = PACKAGES[0].path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGES[0].hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Check if package is stored in cache.
    cache_path = cache.get(PACKAGES[0].hash)
    lms_path = lms_collector.get_path(package)
    assert cache_path == lms_path


async def test_get_non_existing_file(tmp_path_factory: TempPathFactory) -> None:
    lms_collector, cache = create_lms_collector(tmp_path_factory)

    package_bytes = PACKAGES[0].path.read_bytes()
    hash_container = HashContainer(package_bytes, PACKAGES[0].hash)

    # Put package into collector.
    package = await lms_collector.put(hash_container)

    # Remove package from cache.
    await cache.remove(PACKAGES[0].hash)

    with pytest.raises(FileNotFoundError):
        lms_collector.get_path(package)
