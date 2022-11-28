from abc import ABC, abstractmethod
from pathlib import Path

from questionpy_common.manifest import Manifest

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.package import Package


class BaseCollector(ABC):
    """
    A collector responsible for getting packages from a source.
    """

    _worker_pool: WorkerPool

    def __init__(self, worker_pool: WorkerPool):
        self._worker_pool = worker_pool

    async def _get_manifest(self, path: Path) -> Manifest:
        async with self._worker_pool.get_worker(path, 0, None) as worker:
            return await worker.get_manifest()

    async def _create_package(self, package_hash: str, path: Path) -> Package:
        manifest = await self._get_manifest(path)
        return Package(package_hash, manifest, self, path)

    @abstractmethod
    async def get_path(self, package: Package) -> Path:
        """
        Get the path of a package.

        :param package: The package to get the path of.
        :raises FileNotFoundError: If the collector does not contain the package.
        :return: The path of the package.
        """
        raise NotImplementedError

    @abstractmethod
    async def get(self, package_hash: str) -> Package:
        """
        Get a package by its hash.

        :param package_hash: The hash of the package to get.
        :raises FileNotFoundError: If the collector does not contain the package.
        :return: The package.
        """
        raise NotImplementedError


class FixedCollector(BaseCollector, ABC):
    """
    A collector that gets packages from a fixed source, e.g. a local directory or a remote repository.
    """

    @abstractmethod
    async def get_packages(self) -> set[Package]:
        """
        Get all available packages from the source.

        :return: A set of packages.
        """
        raise NotImplementedError


class CachedCollector(BaseCollector, ABC):
    """
    A collector that caches retrieved packages locally.
    """

    _cache: FileLimitLRU

    def __init__(self, cache: FileLimitLRU, worker_pool: WorkerPool):
        super().__init__(worker_pool)
        self._cache = cache
