"""
Contains tests applicable to all worker implementations.
"""
# Stop pylint complaining about fixtures.
# pylint: disable=redefined-outer-name

import pytest
from questionpy_common.constants import MiB

from questionpy_server import WorkerPool
from questionpy_server.worker.runtime.messages import GetQPyPackageManifest
from questionpy_server.worker.worker.subprocess import SubprocessWorker
from questionpy_server.worker.worker.thread import ThreadWorker
from tests.conftest import PACKAGE


@pytest.fixture(params=(SubprocessWorker, ThreadWorker))
def pool(request: pytest.FixtureRequest) -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=request.param)


async def test_should_get_manifest(pool: WorkerPool) -> None:
    async with pool.get_worker(PACKAGE.path, 1, 1) as worker:
        response = await worker.send_and_wait_response(GetQPyPackageManifest(path=str(PACKAGE.path)),
                                                       GetQPyPackageManifest.Response)
        assert response.manifest == PACKAGE.manifest
