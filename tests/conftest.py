from enum import Enum
from typing import Callable

import pytest
from _pytest.tmpdir import TempPathFactory
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_server.app import QPyServer
from questionpy_server.settings import Settings, WebserviceSettings, PackageCacheSettings, CollectorSettings, \
    QuestionStateCacheSettings


class PackageName(str, Enum):
    complete = 'complete'
    no_package = 'no_package'
    no_question_state = 'no_question_state'
    nothing = 'nothing'


class Package:
    def __init__(self, package_hash: str, route: Callable[[str], str]):
        self.package_hash = package_hash
        self.question_state_hash = package_hash
        self.route = route(package_hash)


class Packages:
    def __init__(self, route: Callable[[str], str]):
        self.complete: Package = Package(PackageName.complete, route)
        self.no_package: Package = Package(PackageName.no_package, route)
        self.no_question_state: Package = Package(PackageName.no_question_state, route)
        self.nothing: Package = Package(PackageName.nothing, route)


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

    server.package_cache.put(PackageName.complete, b'.')
    server.question_state_cache.put(PackageName.complete, b'{}')
    server.question_state_cache.put(PackageName.no_package, b'{}')
    server.package_cache.put(PackageName.no_question_state, b'{}')

    return server


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)
