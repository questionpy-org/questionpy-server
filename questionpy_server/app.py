from typing import Any

from aiohttp import web

from . import __version__
from .api.routes import routes
from .settings import Settings


class QPyServer:
    def __init__(self, settings: Settings):
        self.settings: Settings = settings
        self.web_app = web.Application()
        self.web_app.add_routes(routes)
        self.web_app['qpy_server_app'] = self

    def start_server(self) -> None:
        port = self.settings.webservice.listen_port

        def print_start(_ignore: Any) -> None:
            print(f"======== Running QuestionPy Application Server {__version__} on port {port} ========")

        web.run_app(self.web_app, host=self.settings.webservice.listen_address, port=port, print=print_start)
