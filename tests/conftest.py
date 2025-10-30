#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import mimetypes
import tempfile
from collections.abc import AsyncGenerator, Iterable
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import pytest
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, MiB
from questionpy_common.environment import PackagePermissions
from questionpy_common.manifest import PackageFile
from questionpy_server.hash import calculate_hash
from questionpy_server.settings import (
    AuthSettings,
    CacheSettings,
    CollectorSettings,
    CompletePackagePermissions,
    EnvironmentVariablesSettings,
    GeneralSettings,
    PackagePermissionsSettings,
    Settings,
    WebserviceSettings,
    WorkerPoolSettings,
)
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.web.app import QPyServer
from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.impl.thread import ThreadWorker
from questionpy_server.worker.pool import WorkerPool
from questionpy_server.worker.runtime.package_location import DirPackageLocation, ZipPackageLocation


@dataclass(unsafe_hash=True)
class TestZipPackage(ZipPackageLocation):
    __test__ = False

    def __init__(self, path: Path):
        super().__init__(path, calculate_hash(path))

        with ZipFile(self.path) as package:
            self.manifest = ComparableManifest.model_validate_json(package.read(f"{DIST_DIR}/{MANIFEST_FILENAME}"))


@dataclass(unsafe_hash=True)
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
        """Unpacks the given ZIP-based package to create a temporary folder-based package."""
        target_dir = tempfile.mkdtemp(prefix="package-", dir=self.temp_package_dir)
        with ZipFile(package.path) as zip_file:
            zip_file.extractall(target_dir)

        return TestDirPackage(Path(target_dir) / DIST_DIR)

    def to_zip_package(self, package: DirPackageLocation, *, include_siblings: Iterable[str] = ()) -> TestZipPackage:
        """Archives the given dist folder to create a temporary ZIP-based package from the given folder-based package.

        By default, only the dist folder is archived. Set [include_siblings][] to also copy selected files from next to
        the dist dir.
        """
        target_filename = tempfile.mktemp(prefix="package-", suffix=".qpy", dir=self.temp_package_dir)
        with ZipFile(target_filename, "w") as zipfile:
            for subpath in package.path.glob("**/*"):
                zipfile.write(subpath, DIST_DIR / subpath.relative_to(package.path))

            for sibling_filename in include_siblings:
                zipfile.write(package.path.parent / sibling_filename, sibling_filename)

        return TestZipPackage(Path(target_filename))


test_data_path = Path(__file__).parent / "test_data"
package_dir = test_data_path / "package"
PACKAGE = TestZipPackage(package_dir / "package_1.qpy")
PACKAGE_2 = TestZipPackage(package_dir / "package_2.qpy")
DEFAULT_PACKAGE_PERMISSIONS = PackagePermissions(**CompletePackagePermissions().model_dump())


@pytest.fixture
def qpy_server(tmp_path_factory: pytest.TempPathFactory) -> QPyServer:
    return QPyServer(
        Settings(
            config_files=(),
            general=GeneralSettings(),
            webservice=WebserviceSettings(listen_address="127.0.0.1", listen_port=0),
            worker_pool=WorkerPoolSettings(type=ThreadWorker),
            permissions=PackagePermissionsSettings(),
            environment_variables=EnvironmentVariablesSettings(),
            cache=CacheSettings(directory=tmp_path_factory.mktemp("qpy_cache")),
            collector=CollectorSettings(),
            auth=AuthSettings(enabled=False),
        )
    )


@pytest.fixture
async def client(qpy_server: QPyServer, aiohttp_client: AiohttpClient) -> TestClient:
    return await aiohttp_client(qpy_server.web_app)


@pytest.fixture
def package_factory(tmp_path_factory: pytest.TempPathFactory) -> TestPackageFactory:
    return TestPackageFactory(tmp_path_factory.mktemp("test_packages"))


@pytest.fixture(params=(SubprocessWorker, ThreadWorker))
async def worker_pool(request: pytest.FixtureRequest) -> AsyncGenerator[WorkerPool]:
    async with WorkerPool(1, 512 * MiB, worker_type=request.param) as pool:
        yield pool
