from asyncio import to_thread
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.abc import FixedCollector, CachedCollector
from questionpy_server.collector.indexer import Indexer
from questionpy_server.misc import calculate_hash
from questionpy_server.package import Package

if TYPE_CHECKING:
    from questionpy_server.web import HashContainer


class LocalCollector(FixedCollector):
    _directory: Path

    # Maps package hashes to their file paths.
    _map: dict[str, Path] = {}

    def __init__(self, directory: Path, worker_pool: WorkerPool):
        super().__init__(worker_pool=worker_pool)
        self._directory = directory

        for file in self._directory.iterdir():
            if file.suffix == '.qpy':
                package_hash = calculate_hash(file)
                self._map[package_hash] = file

    def get_path_by_hash(self, package_hash: str) -> Path:
        file = self._map.get(package_hash, None)

        if file is None or not file.is_file():
            raise FileNotFoundError

        return file

    async def get(self, package_hash: str) -> Package:
        file = self.get_path_by_hash(package_hash)
        return await self._create_package(package_hash, file)

    async def get_packages(self) -> set[Package]:
        packages: set[Package] = set()

        for file in await to_thread(self._directory.iterdir):
            if file.suffix == '.qpy':
                package_hash = await to_thread(calculate_hash, file)
                package = await self._create_package(package_hash, file)
                packages.add(package)

        return packages

    async def get_path(self, package: Package) -> Path:
        return self.get_path_by_hash(package.hash)


class RepoCollector(FixedCollector, CachedCollector):
    _url: str

    def __init__(self, cache: FileLimitLRU, url: str, worker_pool: WorkerPool):
        super().__init__(cache=cache, worker_pool=worker_pool)
        self._url = url

    async def get(self, package_hash: str) -> Package:
        raise FileNotFoundError

    async def get_path(self, package: Package) -> Path:
        raise FileNotFoundError

    async def get_packages(self) -> set[Package]:
        return set()


class LMSCollector(CachedCollector):
    def __init__(self, cache: FileLimitLRU, worker_pool: WorkerPool):
        super().__init__(cache=cache, worker_pool=worker_pool)

    async def get_path(self, package: Package) -> Path:
        return self._cache.get(package.hash)

    async def get(self, package_hash: str) -> Package:
        file = self._cache.get(package_hash)
        return await self._create_package(package_hash, file)

    async def put(self, package_container: 'HashContainer') -> Package:
        file = await self._cache.put(package_container.hash, package_container.data)
        package = await self._create_package(package_container.hash, file)
        return package


class PackageCollector:
    def __init__(self, local_dir: Optional[Path], repo_urls: list[str], cache: FileLimitLRU, worker_pool: WorkerPool):
        self._cache = cache
        self._worker_pool = worker_pool
        self._collectors: list[FixedCollector] = []

        if local_dir:
            local_collector = LocalCollector(local_dir, self._worker_pool)
            self._collectors.append(local_collector)

        for repo_url in repo_urls:
            repo_collector = RepoCollector(self._cache, repo_url, self._worker_pool)
            self._collectors.append(repo_collector)

        self._lms_collector = LMSCollector(self._cache, self._worker_pool)

        self._indexer = Indexer(self._collectors)

        # Update indexer if package in cache gets removed.
        self._cache.on_remove = self._indexer.unregister_package

    async def put(self, package_container: 'HashContainer') -> Package:
        """
        Handles package send by an LMS.

        :param package_container: package container
        :return: package
        """

        if package := await self._indexer.get_by_hash(package_container.hash):
            return package

        package = await self._lms_collector.put(package_container)
        self._indexer.register_package(package, from_lms=True)
        return package

    async def get(self, package_hash: str) -> Package:
        """
        Returns a package if it exists.

        :param package_hash: hash value of the package
        :return: path to the package
        """

        # Check if package was indexed
        if package := await self._indexer.get_by_hash(package_hash):
            return package

        for collector in self._collectors:
            try:
                package = await collector.get(package_hash)
                self._indexer.register_package(package)
                return package
            except FileNotFoundError:
                continue

        raise FileNotFoundError(f'Package with {package_hash=} was not found.')

    async def get_by_name(self, short_name: str) -> dict[str, Package]:
        """
        Returns a dict of packages with the given short name and available versions.

        :param short_name: short name of the package
        :return: dict of packages and versions
        """

        return await self._indexer.get_by_name(short_name)

    async def get_by_name_and_version(self, short_name: str, version: str) -> Package:
        """
        Returns a package with the given short name and version.

        :param short_name: short name of the package
        :param version: version of the package
        :return: package
        """

        if package := await self._indexer.get_by_name_and_version(short_name, version):
            return package
        raise FileNotFoundError(f'Package with {short_name=} and {version=} was not found.')

    async def get_packages(self) -> set[Package]:
        """
        Returns a set of all available packages.

        :return: set of packages
        """

        return await self._indexer.get_packages()
