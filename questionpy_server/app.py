#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from asyncio import create_task
from typing import Any, ClassVar

from aiohttp import web

from . import __version__
from .cache import FileLimitLRU
from .collector import PackageCollection
from .settings import Settings
from .worker.pool import WorkerPool


class QPyServer:
    APP_KEY: ClassVar[web.AppKey["QPyServer"]] = web.AppKey("qpy_server_app")

    def __init__(self, settings: Settings):
        # We import here, so we don't have to work around circular imports.
        from .api.routes import routes  # noqa: PLC0415

        self.settings: Settings = settings
        self.web_app = web.Application(client_max_size=settings.webservice.max_main_size)
        self.web_app.add_routes(routes)
        self.web_app[self.APP_KEY] = self

        self.worker_pool = WorkerPool(
            settings.worker.max_workers, settings.worker.max_memory, worker_type=settings.worker.type
        )

        self.package_cache = FileLimitLRU(
            settings.cache_package.directory, settings.cache_package.size, extension=".qpy", name="PackageCache"
        )
        self.repo_index_cache = FileLimitLRU(
            settings.cache_repo_index.directory, settings.cache_repo_index.size, name="RepoIndexCache"
        )

        self.package_collection = PackageCollection(
            settings.collector.local_directory,
            settings.collector.repositories,
            self.repo_index_cache,
            self.package_cache,
            self.worker_pool,
        )

        self.web_app.on_startup.append(self._start_package_collection)
        self.web_app.on_shutdown.append(self._stop_package_collection)

    async def _start_package_collection(self, _app: web.Application) -> None:
        # The server will not wait until all package collectors are started. This is done in the background.
        # TODO: 💣 manage or await this task
        create_task(self.package_collection.start())  # noqa: RUF006

    async def _stop_package_collection(self, _app: web.Application) -> None:
        # Wait until all package collectors are stopped appropriately.
        await self.package_collection.stop()

    def start_server(self) -> None:
        port = self.settings.webservice.listen_port

        def print_start(_ignore: Any) -> None:
            print(f"======== Running QuestionPy Application Server {__version__} on port {port} ========")  # noqa: T201

        web.run_app(self.web_app, host=self.settings.webservice.listen_address, port=port, print=print_start)
