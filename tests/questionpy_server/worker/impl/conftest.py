#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from importlib import import_module
from unittest.mock import patch

from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.impl.thread import ThreadWorker
from questionpy_server.worker.pool import WorkerPool
from questionpy_server.worker.runtime.subprocess_main import subprocess_runtime_main


def _custom_runtime_main(patcher_module: str, patcher_name: str) -> None:
    patcher = getattr(import_module(patcher_module), patcher_name)
    with patcher():
        subprocess_runtime_main()


@contextmanager
def patch_worker_pool(worker_pool: WorkerPool, patcher: Callable[[], AbstractContextManager[None]]) -> Iterator[None]:
    if worker_pool._worker_type == ThreadWorker:
        with patcher():
            yield
    elif worker_pool._worker_type == SubprocessWorker:
        # Can't patch stuff inside subprocess, so we use an entrypoint wrapper.
        with patch.object(
            SubprocessWorker,
            "_runtime_main",
            ["-c", f"import {__name__}; {__name__}._custom_runtime_main('{patcher.__module__}', '{patcher.__name__}')"],
        ):
            yield
    else:
        msg = "Expected ThreadWorker or SubprocessWorker"
        raise TypeError(msg)
