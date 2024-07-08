#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import resource
from unittest.mock import patch

import pytest

from questionpy_common.constants import MiB
from questionpy_server import WorkerPool
from questionpy_server.worker.impl.thread import ThreadWorker
from tests.conftest import PACKAGE


@pytest.fixture
def pool() -> WorkerPool:
    return WorkerPool(1, 512 * MiB, worker_type=ThreadWorker)


async def test_should_ignore_limits(pool: WorkerPool) -> None:
    with patch.object(resource, "setrlimit") as mock:
        async with pool.get_worker(PACKAGE, 1, 1):
            pass

        mock.assert_not_called()
