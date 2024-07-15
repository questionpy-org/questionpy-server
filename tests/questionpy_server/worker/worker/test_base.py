#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import mimetypes
from collections.abc import Iterator
from contextlib import AsyncExitStack, contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from zipfile import ZipFile

import pytest

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, MiB
from questionpy_common.manifest import Manifest, PackageFile
from questionpy_server import WorkerPool
from questionpy_server.worker.runtime.package_location import DirPackageLocation, PackageLocation, ZipPackageLocation
from questionpy_server.worker.worker.base import StaticFileSizeMismatchError
from questionpy_server.worker.worker.subprocess import SubprocessWorker
from questionpy_server.worker.worker.thread import ThreadWorker
from tests.conftest import PACKAGE


@pytest.fixture(params=(SubprocessWorker, ThreadWorker))
def pool(request: pytest.FixtureRequest) -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=request.param)


async def test_should_get_manifest(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE, 1, 1) as worker:
        manifest = await worker.get_manifest()
        assert manifest == PACKAGE.manifest


# TODO: Include a test package with actual static files instead of whatever this is.


@contextmanager
def _temp_zip_package(dir_package: DirPackageLocation) -> Iterator[ZipPackageLocation]:
    """Creates a temporary zip package from the given dir package."""
    with NamedTemporaryFile(suffix=".qpy") as file:
        with ZipFile(file, "w") as zipfile:
            for path in dir_package.path.glob("**/*"):
                zipfile.write(path, DIST_DIR / path.relative_to(dir_package.path))

        yield ZipPackageLocation(Path(file.name))


def _inject_static_file_into_dist(package: DirPackageLocation, name: str, content: str) -> None:
    full_path = package.path / name
    full_path.parent.mkdir(exist_ok=True)
    full_path.write_text(content)


def _inject_static_file_into_manifest(package: DirPackageLocation, name: str, size: int) -> None:
    manifest_path = package.path / MANIFEST_FILENAME
    manifest = Manifest.model_validate_json(manifest_path.read_bytes())
    manifest.static_files[name] = PackageFile(mime_type=mimetypes.guess_type(name)[0], size=size)
    manifest_path.write_text(manifest.model_dump_json())


_STATIC_FILE_NAME = "static/test_file.txt"
_STATIC_FILE_CONTENT = "static example file\n"


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_get_static_file(pool: WorkerPool, package_type: Literal["dir", "zip"]) -> None:
    async with AsyncExitStack() as stack:
        dir_package = stack.enter_context(PACKAGE.as_dir_package())
        _inject_static_file_into_dist(dir_package, _STATIC_FILE_NAME, _STATIC_FILE_CONTENT)
        _inject_static_file_into_manifest(dir_package, _STATIC_FILE_NAME, len(_STATIC_FILE_CONTENT))

        package: PackageLocation = (
            dir_package if package_type == "dir" else stack.enter_context(_temp_zip_package(dir_package))
        )

        worker = await stack.enter_async_context(pool.get_worker(package, 1, 1))
        static_file = await worker.get_static_file(_STATIC_FILE_NAME)
        assert static_file.data == _STATIC_FILE_CONTENT.encode()
        assert static_file.mime_type == "text/plain"
        assert static_file.size == len(_STATIC_FILE_CONTENT)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_not_in_manifest(
    pool: WorkerPool, package_type: Literal["dir", "zip"]
) -> None:
    async with AsyncExitStack() as stack:
        dir_package = stack.enter_context(PACKAGE.as_dir_package())
        _inject_static_file_into_dist(dir_package, _STATIC_FILE_NAME, _STATIC_FILE_CONTENT)

        package: PackageLocation = (
            dir_package if package_type == "dir" else stack.enter_context(_temp_zip_package(dir_package))
        )

        worker = await stack.enter_async_context(pool.get_worker(package, 1, 1))
        with pytest.raises(FileNotFoundError):
            await worker.get_static_file(_STATIC_FILE_NAME)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_not_on_disk(
    pool: WorkerPool, package_type: Literal["dir", "zip"]
) -> None:
    async with AsyncExitStack() as stack:
        dir_package = stack.enter_context(PACKAGE.as_dir_package())
        _inject_static_file_into_manifest(dir_package, _STATIC_FILE_NAME, len(_STATIC_FILE_CONTENT))

        package: PackageLocation = (
            dir_package if package_type == "dir" else stack.enter_context(_temp_zip_package(dir_package))
        )

        worker = await stack.enter_async_context(pool.get_worker(package, 1, 1))
        with pytest.raises(FileNotFoundError):
            await worker.get_static_file(_STATIC_FILE_NAME)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_static_file_size_mismatch_error_when_sizes_dont_match(
    pool: WorkerPool, package_type: Literal["dir", "zip"]
) -> None:
    async with AsyncExitStack() as stack:
        dir_package = stack.enter_context(PACKAGE.as_dir_package())
        _inject_static_file_into_dist(dir_package, _STATIC_FILE_NAME, _STATIC_FILE_CONTENT)
        _inject_static_file_into_manifest(dir_package, _STATIC_FILE_NAME, 1234)

        package: PackageLocation = (
            dir_package if package_type == "dir" else stack.enter_context(_temp_zip_package(dir_package))
        )

        worker = await stack.enter_async_context(pool.get_worker(package, 1, 1))
        with pytest.raises(StaticFileSizeMismatchError):
            await worker.get_static_file(_STATIC_FILE_NAME)
