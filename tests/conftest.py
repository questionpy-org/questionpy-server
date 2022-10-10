from functools import cache
from hashlib import sha256
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_server.app import QPyServer
from questionpy_server.settings import Settings, WebserviceSettings, PackageCacheSettings, CollectorSettings, \
    QuestionStateCacheSettings


@cache
def get_file_hash(file: Path) -> str:
    hash_value = sha256()
    with file.open('rb') as f:
        while chunk := f.read(4096):
            hash_value.update(chunk)
    return hash_value.hexdigest()


@pytest.fixture
def qpy_server(tmp_path_factory: TempPathFactory) -> QPyServer:
    package_cache_directory = str(tmp_path_factory.mktemp('qpy_package_cache'))
    question_state_cache_directory = str(tmp_path_factory.mktemp('qpy_question_state_cache'))

    server = QPyServer(Settings(
        config_files=(),
        webservice=WebserviceSettings(listen_address="127.0.0.1", listen_port=0),
        cache_package=PackageCacheSettings(directory=package_cache_directory),
        cache_question_state=QuestionStateCacheSettings(directory=question_state_cache_directory),
        collector=CollectorSettings()
    ))

    return server


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)
