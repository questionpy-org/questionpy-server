#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from asyncio import Task, create_task, sleep
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.abc import CachedCollector
from questionpy_server.repository import RepoMeta, RepoPackage, Repository
from questionpy_server.repository.helper import DownloadError
from questionpy_server.utils.logger import URLAdapter

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.package import Package


class RepoCollector(CachedCollector):
    """Handles packages located in a remote repository.

    This collector is responsible for downloading packages from a remote repository and caching them locally.
    """

    def __init__(
        self,
        url: str,
        update_interval: timedelta,
        package_cache: FileLimitLRU,
        repo_index_cache: FileLimitLRU,
        indexer: "Indexer",
    ):
        super().__init__(cache=package_cache, indexer=indexer)

        self._url = url
        self._repository = Repository(self._url, repo_index_cache)

        self._meta: RepoMeta | None = None
        self._index: dict[str, RepoPackage] = {}

        self._update_interval = update_interval

        self._task: Task | None = None

        logger = logging.getLogger("questionpy-server:repo-collector")
        self._log = URLAdapter(logger, {"url": self._url})

    async def start(self) -> None:
        try:
            await self.update(with_log=False)
            self._log.info(
                "Started with %s unique package(s) and an update interval of %s.",
                len(self._index),
                self._update_interval,
            )
        except DownloadError as error:
            self._log.error("Download failed on startup: %s", error)

        # Create updater task even if the initial update failed.
        self._task = create_task(self._updater(), name=f"RepoCollector updater for {self._url}")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _updater(self) -> None:
        update_interval_seconds = self._update_interval.total_seconds()
        while True:
            await sleep(update_interval_seconds)
            try:
                # TODO: retry after a failed update?
                await self.update()
            except DownloadError as error:
                self._log.error("Download failed on update: %s", error)

    async def update(self, with_log: bool = True) -> None:
        new_meta = await self._repository.get_meta()

        # Check if there was an update in the repository.
        if self._meta and self._meta.timestamp >= new_meta.timestamp:
            return
        self._meta = new_meta

        # Get every package.
        new_packages = await self._repository.get_packages(self._meta)

        old_package_hashes = self._index.keys()
        new_package_hashes = new_packages.keys()

        # Unregister removed packages.
        removed_package_hashes = old_package_hashes - new_package_hashes
        for package_hash in removed_package_hashes:
            await self.indexer.unregister_package(package_hash, self)

        # Register added packages.
        added_package_hashes = new_package_hashes - old_package_hashes
        for package_hash in added_package_hashes:
            repo_package = new_packages[package_hash]
            await self.indexer.register_package(package_hash, repo_package.manifest, self)

        self._index = new_packages

        if with_log:
            self._log.info(
                "Updated package index: %d created, %d deleted (total: %d)",
                len(added_package_hashes),
                len(removed_package_hashes),
                len(self._index),
            )

    async def get_path(self, package: "Package") -> Path:
        if not (repo_package := self._index.get(package.hash, None)):
            raise FileNotFoundError

        try:
            package_bytes = await self._repository.get_package(repo_package)
        except DownloadError as error:
            self._log.warning(error)
            raise FileNotFoundError from error

        return await self._cache.put(package.hash, package_bytes)
