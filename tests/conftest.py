import pytest
from aiohttp.test_utils import TestClient
from pytest_aiohttp.plugin import AiohttpClient

from questionpy.app import QPyServer
from questionpy.settings import Settings, WebserviceSettings


@pytest.fixture
async def qpy_server(aiohttp_client: AiohttpClient) -> QPyServer:
    return QPyServer(Settings(
        config_files=[],
        webservice=WebserviceSettings(listen_address="127.0.0.1", listen_port=0)
    ))


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)
