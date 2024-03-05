"""Contains tests applicable to all worker implementations."""
#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

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
    async with pool.get_worker(PACKAGE, 1, 1) as worker:
        manifest = await worker.get_manifest()
        assert manifest == PACKAGE.manifest
