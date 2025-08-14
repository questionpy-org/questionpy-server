#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import resource
from unittest.mock import patch

import pytest

from questionpy_server import WorkerPool
from questionpy_server.worker.impl.thread import ThreadWorker
from tests.conftest import DEFAULT_PACKAGE_PERMISSIONS, PACKAGE


@pytest.mark.parametrize("worker_pool", [ThreadWorker], indirect=True)
async def test_should_ignore_limits(worker_pool: WorkerPool) -> None:
    with patch.object(resource, "setrlimit") as mock:
        async with worker_pool.get_worker(PACKAGE, "tester", "tests", DEFAULT_PACKAGE_PERMISSIONS):
            pass

        mock.assert_not_called()
