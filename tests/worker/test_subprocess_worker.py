"""Contains tests specific to the :class:`SubprocessWorker`."""
#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import resource

import psutil
import pytest

from questionpy_common.constants import MiB
from questionpy_server import WorkerPool
from questionpy_server.worker.worker.subprocess import SubprocessWorker
from tests.conftest import PACKAGE


@pytest.fixture
def pool() -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=SubprocessWorker)


# TODO: Figure out how to provoke errors in the subprocess worker in order to test their handling.


async def test_should_apply_limits(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE, 1, 1) as worker:
        assert isinstance(worker, SubprocessWorker)
        assert worker._proc
        # Python's resource package can only get the rlimit of other processes on Linux, so we use psutil.
        psutil_process = psutil.Process(worker._proc.pid)
        soft, hard = psutil_process.rlimit(resource.RLIMIT_AS)

    assert soft == hard == 200 * MiB
