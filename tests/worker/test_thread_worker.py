"""
Contains tests specific to the :class:`ThreadWorker`.
"""
# Stop pylint complaining about fixtures.
# pylint: disable=redefined-outer-name

import resource
from typing import NoReturn, Any
from unittest.mock import patch

import pytest
from questionpy_common.constants import MiB

from questionpy_server import WorkerPool
from questionpy_server.worker.exception import WorkerUnknownError, WorkerStartError
from questionpy_server.worker.runtime.manager import WorkerManager
from questionpy_server.worker.runtime.messages import GetQPyPackageManifest
from questionpy_server.worker.worker.thread import ThreadWorker
from tests.conftest import PACKAGE


@pytest.fixture
def pool() -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=ThreadWorker)


class MyError(Exception):
    pass


def just_raise(*_: Any) -> NoReturn:
    raise MyError


async def test_should_gracefully_handle_error_in_bootstrap(pool: WorkerPool) -> None:
    with patch.object(WorkerManager, "bootstrap", just_raise):
        with pytest.raises(WorkerStartError):
            async with pool.get_worker(PACKAGE.path, 1, 1):
                pass


async def test_should_gracefully_handle_error_in_loop(pool: WorkerPool) -> None:
    with patch.object(WorkerManager, "on_msg_get_qpy_package_manifest", just_raise):
        async with pool.get_worker(PACKAGE.path, 1, 1) as worker:
            with pytest.raises(WorkerUnknownError):
                await worker.send_and_wait_response(GetQPyPackageManifest(path=str(PACKAGE.path)),
                                                    GetQPyPackageManifest.Response)


async def test_should_ignore_limits(pool: WorkerPool) -> None:
    with patch.object(resource, "setrlimit") as mock:
        async with pool.get_worker(PACKAGE.path, 1, 1):
            pass

        mock.assert_not_called()