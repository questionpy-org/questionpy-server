#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, KiB
from questionpy_server.app import QPyServer
from questionpy_server.settings import (
    CollectorSettings,
    GeneralSettings,
    PackageCacheSettings,
    RepoIndexCacheSettings,
    Settings,
    WebserviceSettings,
    WorkerSettings,
)
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.worker.runtime.package_location import DirPackageLocation, ZipPackageLocation
from questionpy_server.worker.worker.thread import ThreadWorker


def get_file_hash(path: Path) -> str:
    hash_value = sha256()
    with path.open("rb") as file:
        while chunk := file.read(4 * KiB):
            hash_value.update(chunk)
    return hash_value.hexdigest()


@dataclass
class TestPackage(ZipPackageLocation):
    def __init__(self, path: Path):
        super().__init__(path)
        self.hash = get_file_hash(self.path)

        with ZipFile(self.path) as package:
            self.manifest = ComparableManifest.model_validate_json(package.read(f"{DIST_DIR}/{MANIFEST_FILENAME}"))

    @contextmanager
    def as_dir_package(self) -> Iterator[DirPackageLocation]:
        with TemporaryDirectory() as tmp_dir, ZipFile(self.path) as package:
            package.extractall(tmp_dir)
            yield DirPackageLocation(Path(tmp_dir), self.manifest)


test_data_path = Path(__file__).parent / "test_data"
package_dir = test_data_path / "package"
PACKAGE = TestPackage(package_dir / "package_1.qpy")
PACKAGE_2 = TestPackage(package_dir / "package_2.qpy")


@pytest.fixture
def qpy_server(tmp_path_factory: pytest.TempPathFactory) -> QPyServer:
    return QPyServer(
        Settings(
            config_files=(),
            general=GeneralSettings(),
            webservice=WebserviceSettings(listen_address="127.0.0.1", listen_port=0),
            worker=WorkerSettings(type=ThreadWorker),
            cache_package=PackageCacheSettings(directory=tmp_path_factory.mktemp("qpy_package_cache")),
            cache_repo_index=RepoIndexCacheSettings(directory=tmp_path_factory.mktemp("qpy_repo_index_cache")),
            collector=CollectorSettings(),
        )
    )


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)
