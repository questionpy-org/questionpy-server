#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import math
import resource
from unittest.mock import patch

import psutil
import pytest

from questionpy_common.constants import MiB
from questionpy_common.environment import WorkerResourceLimits
from questionpy_server import WorkerPool
from questionpy_server.worker.impl import Worker
from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.runtime.messages import WorkerTimeLimitExceededError
from questionpy_server.worker.runtime.package_location import PackageLocation
from tests.conftest import PACKAGE


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


async def test_should_raise_timout_error(pool: WorkerPool) -> None:
    def worker_init(self: Worker, package: PackageLocation, _: WorkerResourceLimits | None) -> None:
        self.package = package
        # Set the cpu time limit to a small float greater than zero.
        self.limits = WorkerResourceLimits(200 * MiB, math.ulp(0))

    with pytest.raises(WorkerTimeLimitExceededError), patch.object(Worker, "__init__", worker_init):
        async with pool.get_worker(PACKAGE, 1, 1):
            pass
