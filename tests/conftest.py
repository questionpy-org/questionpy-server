import pytest
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_server.app import QPyServer
from questionpy_server.settings import Settings, WebserviceSettings


@pytest.fixture
def qpy_server() -> QPyServer:
    return QPyServer(Settings(
        config_files=(),
        webservice=WebserviceSettings(listen_address="127.0.0.1", listen_port=0)
    ))


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)
