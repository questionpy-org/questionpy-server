#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import TYPE_CHECKING, Literal

import pytest

from questionpy_common.constants import MiB
from questionpy_server import WorkerPool
from questionpy_server.worker.exception import StaticFileSizeMismatchError
from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.impl.thread import ThreadWorker
from tests.conftest import PACKAGE, TestPackageFactory

if TYPE_CHECKING:
    from questionpy_server.worker.runtime.package_location import PackageLocation


@pytest.fixture(params=(SubprocessWorker, ThreadWorker))
def pool(request: pytest.FixtureRequest) -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=request.param)


async def test_should_get_manifest(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE, 1, 1) as worker:
        manifest = await worker.get_manifest()
        assert manifest == PACKAGE.manifest


_STATIC_FILE_NAME = "static/test_file.txt"
_STATIC_FILE_CONTENT = "static example file\n"


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_get_static_file(
    pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file(_STATIC_FILE_NAME, _STATIC_FILE_CONTENT)

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with pool.get_worker(package, 1, 1) as worker:
        static_file = await worker.get_static_file(_STATIC_FILE_NAME)

    assert static_file.data == _STATIC_FILE_CONTENT.encode()
    assert static_file.mime_type == "text/plain"
    assert static_file.size == len(_STATIC_FILE_CONTENT)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_not_in_manifest(
    pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file_into_dist(_STATIC_FILE_NAME, _STATIC_FILE_CONTENT)

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with pool.get_worker(package, 1, 1) as worker:
        with pytest.raises(FileNotFoundError):
            await worker.get_static_file(_STATIC_FILE_NAME)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_not_on_disk(
    pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file_into_manifest(_STATIC_FILE_NAME, len(_STATIC_FILE_CONTENT))

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with pool.get_worker(package, 1, 1) as worker:
        with pytest.raises(FileNotFoundError):
            await worker.get_static_file(_STATIC_FILE_NAME)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_static_file_size_mismatch_error_when_sizes_dont_match(
    pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file_into_dist(_STATIC_FILE_NAME, _STATIC_FILE_CONTENT)
    dir_package.inject_static_file_into_manifest(_STATIC_FILE_NAME, 1234)

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with pool.get_worker(package, 1, 1) as worker:
        with pytest.raises(StaticFileSizeMismatchError):
            await worker.get_static_file(_STATIC_FILE_NAME)
