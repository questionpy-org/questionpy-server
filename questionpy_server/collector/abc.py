from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import FileLimitLRU

if TYPE_CHECKING:
    from questionpy_server.package import Package


class BaseCollector(ABC):
    """
    A collector responsible for getting packages from a source.
    """

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

    def __init__(self, cache: FileLimitLRU):
        self._cache = cache
