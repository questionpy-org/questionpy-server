# pylint: disable=redefined-outer-name

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest
from _pytest.tmpdir import TempPathFactory
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_common.manifest import Manifest

from questionpy_server.app import QPyServer
from questionpy_server.settings import Settings, WebserviceSettings, PackageCacheSettings, CollectorSettings, \
    QuestionStateCacheSettings


def get_file_hash(path: Path) -> str:
    hash_value = sha256()
    with path.open('rb') as file:
        while chunk := file.read(4096):
            hash_value.update(chunk)
    return hash_value.hexdigest()


@dataclass
class TestPackage:
    __test__ = False
    path: Path

    def __post_init__(self) -> None:
        self.hash = get_file_hash(self.path)

        with TemporaryDirectory() as tmp_dir, ZipFile(self.path) as package:
            package.extractall(tmp_dir)
            manifest_path = Path(tmp_dir) / 'qpy_manifest.json'
            self.manifest = Manifest(**json.loads(manifest_path.read_bytes()))


package_dir = Path('tests/test_data/package/')
PACKAGE = TestPackage(package_dir / 'package_1.qpy')
PACKAGE_2 = TestPackage(package_dir / 'package_2.qpy')


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
