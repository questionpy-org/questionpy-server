from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.abc import CachedCollector

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.web import HashContainer
    from questionpy_server.package import Package


class LMSCollector(CachedCollector):
    """
    Handles packages received by an LMS.

    This collector is a bit different from the others, as it does not have a fixed source of packages.
    Instead, it is used to store packages that are received by an LMS. These packages are stored in
    a cache, and can be retrieved exclusively by their hash.
    """

    def __init__(self, cache: FileLimitLRU, indexer: 'Indexer'):
        super().__init__(cache=cache)
        self._indexer = indexer

    async def get_path(self, package: 'Package') -> Path:
        return self._cache.get(package.hash)

    async def put(self, package_container: 'HashContainer') -> 'Package':
        try:
            # Try to get package from cache.
            package_path = self._cache.get(package_container.hash)
        except FileNotFoundError:
            package_path = await self._cache.put(package_container.hash, package_container.data)
        return await self._indexer.register_package(package_container.hash, package_path, self)
