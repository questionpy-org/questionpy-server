#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from asyncio import gather
from datetime import timedelta
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from pydantic import HttpUrl

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.abc import BaseCollector
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.utils.manfiest import SemVer

if TYPE_CHECKING:
    from questionpy_server.web import HashContainer
    from questionpy_server.package import Package


class PackageCollection:
    """Handles packages from a local directory, remote repositories, and packages received by an LMS."""

    def __init__(self, local_dir: Optional[Path], repos: dict[HttpUrl, timedelta], repo_index_cache: FileLimitLRU,
                 package_cache: FileLimitLRU, worker_pool: WorkerPool):
        self._indexer = Indexer(worker_pool)
        self._collectors: list[BaseCollector] = []

        if local_dir:
            local_collector = LocalCollector(local_dir, self._indexer)
            self._collectors.append(local_collector)

        for url, update_interval in repos.items():
            repo_collector = RepoCollector(url, update_interval, package_cache, repo_index_cache, self._indexer)
            self._collectors.append(repo_collector)

        self._lms_collector = LMSCollector(package_cache, self._indexer)
        self._collectors.append(self._lms_collector)

        # Update indexer if package in cache gets removed.
        package_cache.on_remove = self._unregister_package_from_index

    async def start(self) -> None:
        """Starts the package collection."""

        # Get every start()-coroutine of the collectors and start them.
        await gather(*[collector.start() for collector in self._collectors])

    async def stop(self) -> None:
        """Stops the package collection."""
        # Get every stop()-coroutine of the collectors and start them.
        await gather(*[collector.stop() for collector in self._collectors])

    async def _unregister_package_from_index(self, package_hash: str) -> None:
        """This function should be called when a package gets removed from the cache. A package from a repository should
        not be removed from the index, as it might be still available. Therefore, this function only removes packages
        from the index if they were received by an LMS.
        """

        await self._indexer.unregister_package(package_hash, self._lms_collector)

    async def put(self, package_container: 'HashContainer') -> 'Package':
        """Handles a package sent by an LMS.

        Args:
            package_container: package container

        Returns:
            package
        """

        return await self._lms_collector.put(package_container)

    def get(self, package_hash: str) -> 'Package':
        """Returns a package if it exists.

        Args:
          package_hash (str): hash value of the package

        Returns:
          path to the package
        """

        # Check if package was indexed
        if package := self._indexer.get_by_hash(package_hash):
            return package

        raise FileNotFoundError

    def get_by_identifier(self, identifier: str) -> dict[SemVer, 'Package']:
        """Returns a dict of packages with the given identifier and available versions.

        Args:
          identifier (str): identifier of the package

        Returns:
          dict of packages and versions
        """

        return self._indexer.get_by_identifier(identifier)

    def get_by_identifier_and_version(self, identifier: str, version: SemVer) -> 'Package':
        """Returns a package with the given identifier and version.

        Args:
          identifier (str): identifier of the package
          version (str): version of the package

        Returns:
          package
        """

        if package := self._indexer.get_by_identifier_and_version(identifier, version):
            return package

        raise FileNotFoundError

    def get_packages(self) -> set['Package']:
        """Returns a set of all available packages.

        Returns:
            set of packages
        """

        return self._indexer.get_packages()
