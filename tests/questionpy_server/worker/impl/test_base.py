#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn
from unittest.mock import patch

import pytest

from questionpy_server import WorkerPool
from questionpy_server.worker import WorkerState
from questionpy_server.worker.exception import StaticFileSizeMismatchError, WorkerStartError
from questionpy_server.worker.runtime.manager import WorkerManager
from questionpy_server.worker.runtime.messages import WorkerUnknownError
from tests.conftest import DEFAULT_PACKAGE_PERMISSIONS, PACKAGE, TestPackageFactory
from tests.questionpy_server.worker.impl.conftest import patch_worker_pool

if TYPE_CHECKING:
    from questionpy_common.package_location import PackageLocation


async def test_should_get_manifest(worker_pool: WorkerPool) -> None:
    async with worker_pool.get_worker(PACKAGE, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        manifest = await worker.get_manifest()
        assert manifest == PACKAGE.manifest


_STATIC_FILE_NAME = "static/test_file.txt"
_STATIC_FILE_CONTENT = "static example file\n"


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_get_static_file(
    worker_pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file(_STATIC_FILE_NAME, _STATIC_FILE_CONTENT)

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with worker_pool.get_worker(package, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        static_file = await worker.get_static_file(_STATIC_FILE_NAME)

    assert static_file.data == _STATIC_FILE_CONTENT.encode()
    assert static_file.mime_type == "text/plain"
    assert static_file.size == len(_STATIC_FILE_CONTENT)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_not_in_manifest(
    worker_pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file_into_dist(_STATIC_FILE_NAME, _STATIC_FILE_CONTENT)

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with worker_pool.get_worker(package, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        with pytest.raises(FileNotFoundError):
            await worker.get_static_file(_STATIC_FILE_NAME)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_file_is_outside(
    worker_pool: WorkerPool,
    package_factory: TestPackageFactory,
    package_type: Literal["dir", "zip"],
    caplog: pytest.LogCaptureFixture,
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)

    # Write a file next to the dist folder. The worker should refuse to read it and pretend it doesn't exist.
    content = b"top secret!"
    (dir_package.path.parent / "my_secret_file").write_bytes(content)
    dir_package.inject_static_file_into_manifest("static/../../my_secret_file", len(content), "text/plain")

    package: PackageLocation = (
        dir_package
        if package_type == "dir"
        else package_factory.to_zip_package(dir_package, include_siblings=("my_secret_file",))
    )

    async with worker_pool.get_worker(package, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        with caplog.at_level(logging.INFO), pytest.raises(FileNotFoundError):
            await worker.get_static_file("static/../../my_secret_file")

    assert "Refusing to serve" in caplog.text


async def test_should_raise_file_not_found_error_when_symlink_target_is_outside(
    worker_pool: WorkerPool, package_factory: TestPackageFactory, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    package = package_factory.to_dir_package(PACKAGE)

    content = b"top secret!"
    secret_file_path = tmp_path / "my_secret_file"
    secret_file_path.write_bytes(content)
    (package.path / "static").mkdir(parents=True, exist_ok=True)
    (package.path / "static" / "my_secret_file").symlink_to(secret_file_path)

    package.inject_static_file_into_manifest("static/my_secret_file", len(content), "text/plain")

    async with worker_pool.get_worker(package, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        with caplog.at_level(logging.INFO), pytest.raises(FileNotFoundError):
            await worker.get_static_file("static/my_secret_file")

    assert "Refusing to serve" in caplog.text


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_file_not_found_error_when_not_on_disk(
    worker_pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file_into_manifest(_STATIC_FILE_NAME, len(_STATIC_FILE_CONTENT))

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with worker_pool.get_worker(package, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        with pytest.raises(FileNotFoundError):
            await worker.get_static_file(_STATIC_FILE_NAME)


@pytest.mark.parametrize("package_type", ["dir", "zip"])
async def test_should_raise_static_file_size_mismatch_error_when_sizes_dont_match(
    worker_pool: WorkerPool, package_factory: TestPackageFactory, package_type: Literal["dir", "zip"]
) -> None:
    dir_package = package_factory.to_dir_package(PACKAGE)
    dir_package.inject_static_file_into_dist(_STATIC_FILE_NAME, _STATIC_FILE_CONTENT)
    dir_package.inject_static_file_into_manifest(_STATIC_FILE_NAME, 1234)

    package: PackageLocation = dir_package if package_type == "dir" else package_factory.to_zip_package(dir_package)

    async with worker_pool.get_worker(package, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
        with pytest.raises(StaticFileSizeMismatchError):
            await worker.get_static_file(_STATIC_FILE_NAME)


class MyError(Exception):
    pass


def _just_raise(*_: object) -> NoReturn:
    msg = "some custom error"
    raise MyError(msg)


@contextmanager
def _make_bootstrap_raise() -> Iterator[None]:
    with patch.object(WorkerManager, "bootstrap", _just_raise):
        yield


@contextmanager
def _make_get_manifest_raise() -> Iterator[None]:
    with patch.object(WorkerManager, "on_msg_get_qpy_package_manifest", _just_raise):
        yield


@pytest.mark.filterwarnings("ignore:Exception in thread worker-")
async def test_should_gracefully_handle_error_in_bootstrap(worker_pool: WorkerPool) -> None:
    with patch_worker_pool(worker_pool, _make_bootstrap_raise), pytest.raises(WorkerStartError):
        async with worker_pool.get_worker(PACKAGE, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}):
            pass


async def test_should_gracefully_handle_error_in_loop(worker_pool: WorkerPool) -> None:
    with patch_worker_pool(worker_pool, _make_get_manifest_raise):
        async with worker_pool.get_worker(PACKAGE, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS, {}) as worker:
            with pytest.raises(WorkerUnknownError, match="some custom error"):
                await worker.get_manifest()

            assert worker.state == WorkerState.IDLE
