# pylint: disable=redefined-outer-name
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest
from _pytest.tmpdir import TempPathFactory
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient
from questionpy_common.constants import KiB

from questionpy_server.app import QPyServer
from questionpy_server.settings import Settings, WebserviceSettings, PackageCacheSettings, CollectorSettings, \
    QuestionStateCacheSettings, WorkerSettings
from questionpy_server.worker.runtime.package import QPyPackage


def get_file_hash(path: Path) -> str:
    hash_value = sha256()
    with path.open('rb') as file:
        while chunk := file.read(4 * KiB):
            hash_value.update(chunk)
    return hash_value.hexdigest()


@dataclass
class TestPackage:
    __test__ = False
    path: Path

    def __post_init__(self) -> None:
        self.hash = get_file_hash(self.path)

        with QPyPackage(self.path) as package:
            self.manifest = package.manifest


package_dir = Path(__file__).parent / 'test_data/package'
PACKAGE = TestPackage(package_dir / 'package_1.qpy')
PACKAGE_2 = TestPackage(package_dir / 'package_2.qpy')


@pytest.fixture
def qpy_server(tmp_path_factory: TempPathFactory) -> QPyServer:
    package_cache_directory = tmp_path_factory.mktemp('qpy_package_cache')
    question_state_cache_directory = tmp_path_factory.mktemp('qpy_question_state_cache')

    server = QPyServer(Settings(
        config_files=(),
        webservice=WebserviceSettings(listen_address="127.0.0.1", listen_port=0),
        worker=WorkerSettings(),
        cache_package=PackageCacheSettings(directory=package_cache_directory),
        cache_question_state=QuestionStateCacheSettings(directory=question_state_cache_directory),
        collector=CollectorSettings()
    ))

    return server


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)
