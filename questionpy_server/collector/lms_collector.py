#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector.abc import CachedCollector

if TYPE_CHECKING:
    from questionpy_server.collector.indexer import Indexer
    from questionpy_server.web import HashContainer
    from questionpy_server.package import Package


class LMSCollector(CachedCollector):
    """Handles packages received by an LMS.

    This collector is a bit different from the others, as it does not have a fixed source of packages.
    Instead, it is used to store packages that are received by an LMS. These packages are stored in
    a cache, and can be retrieved exclusively by their hash.
    """

    def __init__(self, cache: FileLimitLRU, indexer: "Indexer"):
        super().__init__(cache=cache, indexer=indexer)

    async def start(self) -> None:
        count = 0
        # We assume that existing packages in the cache are from an LMS as it has the most strict visibility i.e. the
        # package can only be accessed by the hash.
        for package_hash, file in self._cache.files.items():
            await self.indexer.register_package(package_hash, file.path, self)
            count += 1

        log = logging.getLogger("questionpy-server:lms-collector")
        log.info("Started with %s package(s).", count)

    async def get_path(self, package: "Package") -> Path:
        return self._cache.get(package.hash)

    async def put(self, package_container: "HashContainer") -> "Package":
        try:
            # Try to get package from cache.
            package_path = self._cache.get(package_container.hash)
        except FileNotFoundError:
            package_path = await self._cache.put(package_container.hash, package_container.data)
        return await self.indexer.register_package(package_container.hash, package_path, self)
