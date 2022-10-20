from typing import Any

from aiohttp import web

from . import __version__
from .api.routes import routes
from .cache import FileLimitLRU
from .collector import PackageCollector
from .settings import Settings
from .worker.controller import WorkerPool


class QPyServer:
    def __init__(self, settings: Settings):
        self.settings: Settings = settings
        self.web_app = web.Application(client_max_size=settings.webservice.max_bytes_main)
        self.web_app.add_routes(routes)
        self.web_app['qpy_server_app'] = self
        self.worker_pool = WorkerPool(0, 0)

        self.package_cache = FileLimitLRU(settings.cache_package.directory, settings.cache_package.size,
                                          extension='.qpy', name='PackageCache')
        self.collector = PackageCollector(settings.collector.local_directory, [], self.package_cache, self.worker_pool)
        self.question_state_cache = FileLimitLRU(settings.cache_question_state.directory,
                                                 settings.cache_question_state.size, name='QuestionStateCache')

    def start_server(self) -> None:
        port = self.settings.webservice.listen_port

        def print_start(_ignore: Any) -> None:
            print(f"======== Running QuestionPy Application Server {__version__} on port {port} ========")

        web.run_app(self.web_app, host=self.settings.webservice.listen_address, port=port, print=print_start)
