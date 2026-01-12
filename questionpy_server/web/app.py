#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar

from aiohttp import web

from questionpy_server import __version__
from questionpy_server.cache import LRUCache, LRUCacheSupervisor
from questionpy_server.collector import PackageCollection
from questionpy_server.dependencies import PackageCollectionDependencyResolver
from questionpy_server.settings import Settings
from questionpy_server.web.middlewares import middlewares
from questionpy_server.worker.pool import WorkerPool
from questionpy_server.worker.selector.environment_variables import EnvironmentVariablesHandler
from questionpy_server.worker.selector.permissions import PackagePermissionsHandler

_log = logging.getLogger(__name__)


class QPyServer:
    APP_KEY: ClassVar[web.AppKey["QPyServer"]] = web.AppKey("qpy_server_app")

    def __init__(self, settings: Settings):
        # We import here, so we don't have to work around circular imports.
        from questionpy_server.web._routes import routes  # noqa: PLC0415

        self.settings: Settings = settings
        self.web_app = web.Application(client_max_size=settings.webservice.max_main_size, middlewares=middlewares)
        self.web_app.add_routes(routes)
        self.web_app[self.APP_KEY] = self

        self.package_permissions = PackagePermissionsHandler(settings.permissions)
        self.environment_variables = EnvironmentVariablesHandler(settings.environment_variables)

        cache_supervisor = LRUCacheSupervisor(settings.cache.directory, settings.cache.size)
        self.package_cache = LRUCache(cache_supervisor, Path("packages"), extension=".qpy")
        self.repo_index_cache = LRUCache(cache_supervisor, Path("repo_index"))

        self.package_collection = PackageCollection(
            settings.collector.local_directory,
            settings.collector.repositories,
            self.repo_index_cache,
            self.package_cache,
        )

        worker_dependency_resolver = PackageCollectionDependencyResolver(self.package_collection)
        self.worker_pool = WorkerPool(
            settings.worker_pool.max_cpus,
            settings.worker_pool.max_memory,
            worker_type=settings.worker_pool.type,
            dependency_resolver=worker_dependency_resolver,
        )

        self.web_app.cleanup_ctx.append(self._worker_pool_ctx)
        self.web_app.cleanup_ctx.append(self._package_collection_ctx)

    async def _worker_pool_ctx(self, _app: web.Application) -> AsyncIterator[None]:
        async with self.worker_pool:
            yield

    async def _package_collection_ctx(self, _app: web.Application) -> AsyncIterator[None]:
        def on_started(task_: asyncio.Task) -> None:
            if e := task_.exception():
                _log.error("Failed to start at least one package collector: %s", str(e), exc_info=e)
            else:
                _log.debug("All package collectors have been started successfully.")

        task = asyncio.create_task(self.package_collection.start(), name="start package collection")
        task.add_done_callback(on_started)

        try:
            yield
        finally:
            # Wait until all package collectors are stopped appropriately.
            await self.package_collection.stop()

    def run_forever(self) -> None:
        """Runs the server. Blocks until shut down by a signal."""
        port = self.settings.webservice.listen_port

        def print_start(_ignore: Any) -> None:
            print(f"======== Running QuestionPy Application Server {__version__} on port {port} ========")  # noqa: T201

        web.run_app(self.web_app, host=self.settings.webservice.listen_address, port=port, print=print_start)
