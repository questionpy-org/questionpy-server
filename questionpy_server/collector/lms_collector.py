#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import LRUCache
from questionpy_server.collector.abc import CachedCollector
from questionpy_server.worker.runtime.messages import BaseWorkerError

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.hash import HashContainer
    from questionpy_server.package import Package


class LMSCollector(CachedCollector):
    """Handles packages received by an LMS.

    This collector is a bit different from the others, as it does not have a fixed source of packages.
    Instead, it is used to store packages that are received by an LMS. These packages are stored in
    a cache, and can be retrieved exclusively by their hash.
    """

    def __init__(self, cache: LRUCache, indexer: "Indexer"):
        super().__init__(cache=cache, indexer=indexer)

    async def start(self) -> None:
        count = 0
        invalid_count = 0
        # We assume that existing packages in the cache are from an LMS as it has the most strict visibility i.e. the
        # package can only be accessed by the hash.
        for package_hash, file in self._cache.files.items():
            try:
                await self.indexer.register_package(package_hash, file.path, self)
                count += 1
            except BaseWorkerError:
                invalid_count += 1
                await self._cache.remove(package_hash)

        log = logging.getLogger("questionpy-server:lms-collector")
        log.info("Started with %s package(s).", count)
        log.debug("Removed %s invalid package(s).", invalid_count)

    async def get_path(self, package: "Package") -> Path:
        return self._cache.get(package.hash)

    async def put(self, package_container: "HashContainer") -> "Package":
        try:
            # Try to get package from cache.
            package_path = self._cache.get(package_container.hash)
        except FileNotFoundError:
            package_path = await self._cache.put(package_container.hash, package_container.data)

        try:
            return await self.indexer.register_package(package_container.hash, package_path, self)
        except BaseWorkerError:
            # Faulty package - remove the file.
            await self._cache.remove(package_container.hash)
            raise
