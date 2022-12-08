from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.abc import CachedCollector

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.package import Package


class RepoCollector(CachedCollector):
    """
    Handles packages located in a remote repository.

    This collector is responsible for downloading packages from a remote repository and caching them locally.
    """

    url: str

    def __init__(self, cache: FileLimitLRU, url: str, indexer: 'Indexer'):
        super().__init__(cache=cache)
        self.url = url
        self._indexer = indexer

    async def get_path(self, package: 'Package') -> Path:
        raise FileNotFoundError
