#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
import itertools
import logging
import sys
import threading
from asyncio import Task
from collections.abc import Sequence

from questionpy_common.environment import WorkerResourceLimits
from questionpy_server.worker.connection import ServerToWorkerConnection
from questionpy_server.worker.exception import WorkerNotRunningError
from questionpy_server.worker.impl._base import BaseWorker
from questionpy_server.worker.runtime.connection import WorkerToServerConnection
from questionpy_server.worker.runtime.manager import WorkerManager
from questionpy_server.worker.runtime.package_location import PackageLocation
from questionpy_server.worker.runtime.streams import AsyncReadAdapter, DuplexPipe

log = logging.getLogger(__name__)


class _WorkerThread(threading.Thread):
    _counter = itertools.count()
    """Counter serving only to give worker threads unique names."""

    def __init__(self, pipe: DuplexPipe) -> None:
        super().__init__(name=f"qpy-worker-{next(self._counter)}", daemon=True)
        self._pipe = pipe
        self._end_event = asyncio.Event()
        self._loop = asyncio.get_running_loop()

    def run(self) -> None:
        self._end_event.clear()

        # sys.path isn't thread-local, so this doesn't isolate concurrently running workers, but since the thread worker
        # is only for testing anyway, it'll do for now.
        original_path = sys.path.copy()
        original_module_names = set(sys.modules.keys())

        connection = WorkerToServerConnection(self._pipe.right, self._pipe.right)
        manager = WorkerManager(connection)
        try:
            manager.bootstrap()
            manager.loop()
        finally:
            # Since asyncio.Event is not threadsafe, we schedule setting it in the main thread instead.
            self._loop.call_soon_threadsafe(self._end_event.set)

            sys.path = original_path
            for module_name in sys.modules.keys() - original_module_names:
                # Having reset the path, this forces questionpy and any package modules to be reloaded upon next import.
                del sys.modules[module_name]

    async def wait(self) -> None:
        await self._end_event.wait()
        self.join()


class ThreadWorker(BaseWorker):
    """Worker implementation using a thread withing the server process for simpler debugging of package code."""

    _worker_type = "thread"

    def __init__(self, package: PackageLocation, limits: WorkerResourceLimits | None) -> None:
        super().__init__(package=package, limits=limits)

        self._pipe: DuplexPipe | None = None

        self._task: Task | None = None

    async def _run_and_wait(self, thread: _WorkerThread) -> None:
        try:
            thread.start()
            await thread.wait()
        finally:
            if self._pipe:
                self._pipe.close()
                self._pipe = None

    async def start(self) -> None:
        if self.limits:
            log.warning("Limits '%s' were given, but thread-based workers don't support resource limits", self.limits)
            self.limits = None

        self._pipe = DuplexPipe.open()
        thread = _WorkerThread(self._pipe)

        self._task = asyncio.create_task(self._run_and_wait(thread), name=thread.name)

        self._connection = ServerToWorkerConnection(AsyncReadAdapter(self._pipe.left), self._pipe.left)

        await self._initialize()

    def _get_observation_tasks(self) -> Sequence[asyncio.Task]:
        if not self._task:
            raise WorkerNotRunningError

        return [
            *super()._get_observation_tasks(),
            self._task,
        ]

    async def kill(self) -> None:
        # Python doesn't actually offer a way to kill a thread.
        # We assume that it was already sent an Exit message.
        pass

    async def get_resource_usage(self) -> None:
        return None
