from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import FileLimitLRU

if TYPE_CHECKING:
    from questionpy_server.package import Package
    from questionpy_server.collector.indexer import Indexer


class BaseCollector(ABC):
    """
    A collector responsible for getting packages from a source.
    """

    indexer: 'Indexer'

    def __init__(self, indexer: 'Indexer'):
        self.indexer = indexer

    @abstractmethod
    async def start(self) -> None:
        """
        Starts the collector.
        """
        raise NotImplementedError

    async def stop(self) -> None:
        """
        Stops the collector.
        """
        return

    async def __aenter__(self) -> 'BaseCollector':
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    @abstractmethod
    async def get_path(self, package: 'Package') -> Path:
        """
        Get the path of a package.

        :param package: The package to get the path of.
        :raises FileNotFoundError: If the collector does not contain the package.
        :return: The path of the package.
        """
        raise NotImplementedError


class CachedCollector(BaseCollector, ABC):
    """
    A collector that caches retrieved packages locally.
    """

    _cache: FileLimitLRU

    def __init__(self, cache: FileLimitLRU, indexer: 'Indexer'):
        super().__init__(indexer=indexer)
        self._cache = cache
