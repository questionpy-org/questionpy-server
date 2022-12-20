from asyncio import run
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.misc import calculate_hash

if TYPE_CHECKING:
    from questionpy_server.web import HashContainer
    from questionpy_server.package import Package


class PackageCollection:
    """
    Handles packages from a local directory, remote repositories, and packages received by an LMS.
    """

    def __init__(self, local_dir: Optional[Path], repo_urls: list[str], cache: FileLimitLRU, worker_pool: WorkerPool):
        self._indexer = Indexer(worker_pool)

        if local_dir:
            local_collector = LocalCollector(local_dir, self._indexer)
            self._local_collector = local_collector

        self._repo_collectors: list[RepoCollector] = []
        for repo_url in repo_urls:
            repo_collector = RepoCollector(cache, repo_url, self._indexer)
            self._repo_collectors.append(repo_collector)

        self._lms_collector = LMSCollector(cache, self._indexer)

        # Register packages which are already in the cache.
        for file in cache.directory.iterdir():
            if file.suffix != '.qpy':
                continue
            # We assume that existing packages from the cache are from an LMS.
            coroutine = self._indexer.register_package(calculate_hash(file), file, self._lms_collector)
            run(coroutine)

        # Update indexer if package in cache gets removed.
        cache.on_remove = self._unregister_package_from_index

    def _unregister_package_from_index(self, package_hash: str) -> None:
        """
        This function should be called when a package gets removed from the cache. A package from a repository should
        not be removed from the index, as it might be still available. Therefore, this function only removes packages
        from the index if they were received by an LMS.
        """

        self._indexer.unregister_package(package_hash, self._lms_collector)

    async def put(self, package_container: 'HashContainer') -> 'Package':
        """
        Handles a package sent by an LMS.

        :param package_container: package container
        :return: package
        """

        return await self._lms_collector.put(package_container)

    def get(self, package_hash: str) -> 'Package':
        """
        Returns a package if it exists.

        :param package_hash: hash value of the package
        :return: path to the package
        """

        # Check if package was indexed
        if package := self._indexer.get_by_hash(package_hash):
            return package

        raise FileNotFoundError

    def get_by_name(self, short_name: str) -> dict[str, 'Package']:
        """
        Returns a dict of packages with the given short name and available versions.

        :param short_name: short name of the package
        :return: dict of packages and versions
        """

        return self._indexer.get_by_name(short_name)

    def get_by_name_and_version(self, short_name: str, version: str) -> 'Package':
        """
        Returns a package with the given short name and version.

        :param short_name: short name of the package
        :param version: version of the package
        :return: package
        """

        if package := self._indexer.get_by_name_and_version(short_name, version):
            return package

        raise FileNotFoundError

    def get_packages(self) -> set['Package']:
        """
        Returns a set of all available packages.

        :return: set of packages
        """

        return self._indexer.get_packages()
