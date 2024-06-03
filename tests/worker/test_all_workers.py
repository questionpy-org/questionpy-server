"""Contains tests applicable to all worker implementations."""
#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import mimetypes
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from questionpy_common.constants import DIST_DIR, MANIFEST_FILENAME, MiB
from questionpy_common.manifest import PackageFile
from questionpy_server import WorkerPool
from questionpy_server.worker.runtime.package_location import DirPackageLocation
from questionpy_server.worker.worker.subprocess import SubprocessWorker
from questionpy_server.worker.worker.thread import ThreadWorker
from tests.conftest import PACKAGE

if TYPE_CHECKING:
    from questionpy_server.worker.worker import Worker


@pytest.fixture(params=(SubprocessWorker, ThreadWorker))
def pool(request: pytest.FixtureRequest) -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=request.param)


async def test_should_get_manifest(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE, 1, 1) as worker:
        manifest = await worker.get_manifest()
        assert manifest == PACKAGE.manifest


# TODO: Include a test package with actual static files instead of whatever this is.


def _inject_static_file_into_dist(package: DirPackageLocation, name: str, content: str) -> None:
    full_path = package.path / f"{DIST_DIR}/{name}"
    full_path.parent.mkdir(exist_ok=True)
    full_path.write_text(content)


def _inject_static_file_into_manifest(package: DirPackageLocation, name: str, size: int) -> None:
    package.manifest = deepcopy(package.manifest)
    package.manifest.static_files[name] = PackageFile(mime_type=mimetypes.guess_type(name)[0], size=size)
    (package.path / DIST_DIR / MANIFEST_FILENAME).write_text(package.manifest.model_dump_json())


_STATIC_FILE_NAME = "static/test_file.txt"
_STATIC_FILE_CONTENT = "static example file\n"


async def test_should_get_static_file_from_dir(pool: WorkerPool) -> None:
    with PACKAGE.as_dir_package() as package:
        _inject_static_file_into_dist(package, _STATIC_FILE_NAME, _STATIC_FILE_CONTENT)
        _inject_static_file_into_manifest(package, _STATIC_FILE_NAME, len(_STATIC_FILE_CONTENT))

        worker: Worker
        async with pool.get_worker(package, 1, 1) as worker:
            static_file = await worker.get_static_file(_STATIC_FILE_NAME)
            assert static_file.data == _STATIC_FILE_CONTENT.encode()
            assert static_file.mime_type == "text/plain"
            assert static_file.size == len(_STATIC_FILE_CONTENT)


async def test_should_raise_FileNotFoundError_when_not_in_manifest(pool: WorkerPool) -> None:
    with PACKAGE.as_dir_package() as package:
        _inject_static_file_into_dist(package, _STATIC_FILE_NAME, _STATIC_FILE_CONTENT)

        worker: Worker
        async with pool.get_worker(package, 1, 1) as worker:
            with pytest.raises(FileNotFoundError):
                await worker.get_static_file(_STATIC_FILE_NAME)


async def test_should_raise_FileNotFoundError_when_not_on_disk(pool: WorkerPool) -> None:
    with PACKAGE.as_dir_package() as package:
        _inject_static_file_into_manifest(package, _STATIC_FILE_NAME, len(_STATIC_FILE_CONTENT))

        worker: Worker
        async with pool.get_worker(package, 1, 1) as worker:
            with pytest.raises(FileNotFoundError):
                await worker.get_static_file(_STATIC_FILE_NAME)


async def test_should_raise_RuntimeError_when_sizes_dont_match(pool: WorkerPool) -> None:
    with PACKAGE.as_dir_package() as package:
        _inject_static_file_into_dist(package, _STATIC_FILE_NAME, _STATIC_FILE_CONTENT)
        _inject_static_file_into_manifest(package, _STATIC_FILE_NAME, 1234)

        worker: Worker
        async with pool.get_worker(package, 1, 1) as worker:
            with pytest.raises(RuntimeError):
                await worker.get_static_file(_STATIC_FILE_NAME)
