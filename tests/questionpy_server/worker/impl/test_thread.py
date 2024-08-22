#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import resource
from typing import Any, NoReturn
from unittest.mock import patch

import pytest

from questionpy_common.constants import MiB
from questionpy_server import WorkerPool
from questionpy_server.worker.exception import WorkerStartError
from questionpy_server.worker.impl.thread import ThreadWorker
from questionpy_server.worker.runtime.manager import WorkerManager
from questionpy_server.worker.runtime.messages import WorkerUnknownError
from tests.conftest import PACKAGE


@pytest.fixture
def pool() -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=ThreadWorker)


class MyError(Exception):
    pass


def just_raise(*_: Any) -> NoReturn:
    raise MyError


@pytest.mark.filterwarnings("ignore:Exception in thread qpy-worker-")
async def test_should_gracefully_handle_error_in_bootstrap(pool: WorkerPool) -> None:
    with patch.object(WorkerManager, "bootstrap", just_raise), pytest.raises(WorkerStartError):
        async with pool.get_worker(PACKAGE, 1, 1):
            pass


@pytest.mark.filterwarnings("ignore:Exception in thread qpy-worker-")
async def test_should_gracefully_handle_error_in_loop(pool: WorkerPool) -> None:
    with patch.object(WorkerManager, "on_msg_get_qpy_package_manifest", just_raise):
        async with pool.get_worker(PACKAGE, 1, 1) as worker:
            with pytest.raises(WorkerUnknownError):
                await worker.get_manifest()


async def test_should_ignore_limits(pool: WorkerPool) -> None:
    with patch.object(resource, "setrlimit") as mock:
        async with pool.get_worker(PACKAGE, 1, 1):
            pass

        mock.assert_not_called()
