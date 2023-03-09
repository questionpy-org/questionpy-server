"""
Contains tests applicable to all worker implementations.
"""
# Stop pylint complaining about fixtures.
# pylint: disable=redefined-outer-name

import pytest
from questionpy_common.constants import MiB

from questionpy_server import WorkerPool
from questionpy_server.worker.worker.subprocess import SubprocessWorker
from questionpy_server.worker.worker.thread import ThreadWorker
from tests.conftest import PACKAGE


@pytest.fixture(params=(SubprocessWorker, ThreadWorker))
def pool(request: pytest.FixtureRequest) -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=request.param)


async def test_should_get_manifest(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE.path, 1, 1) as worker:
        manifest = await worker.get_manifest()
        assert manifest == PACKAGE.manifest
