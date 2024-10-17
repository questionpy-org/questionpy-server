#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import resource
from collections.abc import Iterator
from contextlib import contextmanager
from time import process_time, sleep, time
from unittest.mock import patch

import psutil
import pytest

from questionpy_common.constants import MiB
from questionpy_server import WorkerPool
from questionpy_server.worker.exception import (
    WorkerCPUTimeLimitExceededError,
    WorkerRealTimeLimitExceededError,
    WorkerStartError,
)
from questionpy_server.worker.impl._base import BaseWorker, LimitTimeUsageMixin
from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.runtime.manager import WorkerManager
from tests.conftest import PACKAGE
from tests.questionpy_server.worker.impl.conftest import patch_worker_pool


@pytest.fixture
def pool() -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=SubprocessWorker)


async def test_should_apply_limits(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE, 1, 1) as worker:
        assert isinstance(worker, SubprocessWorker)
        assert worker._proc
        # Python's resource package can only get the rlimit of other processes on Linux, so we use psutil.
        psutil_process = psutil.Process(worker._proc.pid)
        soft, hard = psutil_process.rlimit(resource.RLIMIT_AS)

    assert soft == hard == 200 * MiB


@contextmanager
def _make_get_manifest_busy_wait() -> Iterator[None]:
    def busy_wait(self: WorkerManager) -> None:
        wait_until = process_time() + 10
        while wait_until > process_time():
            pass

    with patch.object(WorkerManager, "bootstrap", busy_wait):
        yield


async def test_should_raise_cpu_timout_error(pool: WorkerPool) -> None:
    with patch_worker_pool(pool, _make_get_manifest_busy_wait):
        start_time = time()
        # Change the timeout for faster testing.
        with pytest.raises(WorkerStartError) as exc_info, patch.object(BaseWorker, "_init_worker_timeout", 0.05):
            async with pool.get_worker(PACKAGE, 1, 1):
                pass
        assert isinstance(exc_info.value.__cause__, WorkerCPUTimeLimitExceededError)
        assert 0.05 < (time() - start_time) < 0.5


@contextmanager
def _make_get_manifest_sleep() -> Iterator[None]:
    def _sleep(self: WorkerManager) -> None:
        sleep(10)

    with patch.object(WorkerManager, "bootstrap", _sleep):
        yield


async def test_should_raise_real_timout_error(pool: WorkerPool) -> None:
    with patch_worker_pool(pool, _make_get_manifest_sleep):
        # The timeout should not be too short, because the Python interpreter also needs some time to start up, which
        # is accounted for the init worker step. Otherwise, a WorkerCPUTimeLimitExceededError is raised.
        start_time = time()
        with (
            pytest.raises(WorkerStartError) as exc_info,
            # Change the timeout and factor for faster testing.
            patch.object(BaseWorker, "_init_worker_timeout", 0.6),
            patch.object(LimitTimeUsageMixin, "_real_time_limit_factor", 1.0),
        ):
            async with pool.get_worker(PACKAGE, 1, 1) as worker:
                await worker.get_manifest()
        assert isinstance(exc_info.value.__cause__, WorkerRealTimeLimitExceededError)
        assert 0.6 < (time() - start_time) < 2.0
