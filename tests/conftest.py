#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import mimetypes
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, KiB
from questionpy_common.manifest import PackageFile
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
from questionpy_server.web.app import QPyServer
from questionpy_server.worker.runtime.package_location import DirPackageLocation, ZipPackageLocation
from questionpy_server.worker.worker.thread import ThreadWorker


def get_file_hash(path: Path) -> str:
    hash_value = sha256()
    with path.open("rb") as file:
        while chunk := file.read(4 * KiB):
            hash_value.update(chunk)
    return hash_value.hexdigest()


@dataclass
class TestZipPackage(ZipPackageLocation):
    __test__ = False

    def __init__(self, path: Path):
        super().__init__(path)

        self.hash = get_file_hash(self.path)
        with ZipFile(self.path) as package:
            self.manifest = ComparableManifest.model_validate_json(package.read(f"{DIST_DIR}/{MANIFEST_FILENAME}"))


@dataclass
class TestDirPackage(DirPackageLocation):
    __test__ = False

    def __init__(self, path: Path) -> None:
        super().__init__(path)

        self.manifest = ComparableManifest.model_validate_json((path / MANIFEST_FILENAME).read_text())

    def inject_static_file_into_dist(self, name: str, content: str | bytes) -> int:
        """Inserts a static file only into dist. Can be used to produce invalid static file configurations."""
        full_path = self.path / name
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            return full_path.write_text(content)
        return full_path.write_bytes(content)

    def inject_static_file_into_manifest(self, name: str, size: int, mime_type: str | None = None) -> None:
        """Inserts a static file only into the manifest. Can be used to produce invalid static file configurations."""
        if mime_type is None:
            mime_type = mimetypes.guess_type(name)[0]

        self.manifest.static_files[name] = PackageFile(mime_type=mime_type, size=size)
        (self.path / MANIFEST_FILENAME).write_text(self.manifest.model_dump_json())

    def inject_static_file(self, name: str, content: str | bytes, mime_type: str | None = None) -> None:
        """Inserts a valid static file both into dist and the manifest."""
        size = self.inject_static_file_into_dist(name, content)
        self.inject_static_file_into_manifest(name, size, mime_type)


class TestPackageFactory:
    """Assists in quickly creating test packages based on [PACKAGE][] and [PACKAGE_2][].

    Since all test packages are created in one temporary directory, tests don't need tons of context managers. Use the
    fixture [package_factory][] to get an instance.
    """

    __test__ = False

    def __init__(self, temp_package_dir: Path) -> None:
        self.temp_package_dir = temp_package_dir

    def to_dir_package(self, package: ZipPackageLocation) -> TestDirPackage:
        target_dir = tempfile.mkdtemp(prefix="package-", dir=self.temp_package_dir)
        with ZipFile(package.path) as zip_file:
            zip_file.extractall(target_dir)

        return TestDirPackage(Path(target_dir) / DIST_DIR)

    def to_zip_package(self, package: DirPackageLocation) -> TestZipPackage:
        target_filename = tempfile.mktemp(prefix="package-", suffix=".qpy", dir=self.temp_package_dir)
        with ZipFile(target_filename, "w") as zipfile:
            for subpath in package.path.glob("**/*"):
                zipfile.write(subpath, DIST_DIR / subpath.relative_to(package.path))

        return TestZipPackage(Path(target_filename))


test_data_path = Path(__file__).parent / "test_data"
package_dir = test_data_path / "package"
PACKAGE = TestZipPackage(package_dir / "package_1.qpy")
PACKAGE_2 = TestZipPackage(package_dir / "package_2.qpy")


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


@pytest.fixture
def package_factory(tmp_path_factory: pytest.TempPathFactory) -> TestPackageFactory:
    return TestPackageFactory(tmp_path_factory.mktemp("test_packages"))
