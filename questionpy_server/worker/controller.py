from asyncio import Semaphore, to_thread, Lock
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from questionpy_common.manifest import Manifest
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.misc import Bytes, ByteSize
from .worker import WorkerProcessBase, WorkerProcess, WorkerResourceLimits
from .runtime.messages import GetQPyPackageManifest, GetOptionsFormDefinition


class Worker:
    def __init__(self, process: WorkerProcessBase):
        self.process: WorkerProcessBase = process

    async def get_manifest(self) -> Manifest:
        """Get manifest of the main package in the worker."""
        msg = GetQPyPackageManifest(path=str(self.process.package))
        ret = await self.process.send_and_wait_response(msg, GetQPyPackageManifest.Response)
        return ret.manifest

    async def get_options_form_definition(self) -> OptionsFormDefinition:
        """Get the package options form definition."""
        msg = GetOptionsFormDefinition()
        ret = await self.process.send_and_wait_response(msg, GetOptionsFormDefinition.Response)
        return ret.definition


class WorkerPool:
    def __init__(self, max_workers: int, max_memory: int):
        """
        Initialize the worker pool.

        :param max_workers: maximum number of workers being executed in parallel
        :param max_memory: maximum memory (in bytes) that all workers in the pool are allowed to consume
        """
        self.max_workers = max_workers
        self.max_memory = max_memory
        self._processes: list[WorkerProcess] = []

        self._semaphore: Optional[Semaphore] = None
        self._lock: Optional[Lock] = None

    def get_current_memory_usage(self) -> Bytes:
        total = 0
        for process in self._processes:
            total += process.get_resource_usage().memory_bytes
        return Bytes(total)

    async def _wait_for_memory(self) -> None:
        while True:
            memory = await to_thread(self.get_current_memory_usage)
            if memory < self.max_memory:
                break

    @asynccontextmanager
    async def get_worker(self, package: Path, lms: int, context: Optional[int]) -> AsyncIterator[Worker]:
        """
        Get a (new) worker executing a QuestionPy package. A context manager is used to ensure
        that a worker is always given back to the pool.

        :param package: path to QuestionPy package
        :param lms: id of the LMS
        :param context: context id within the lms
        :return: a worker
        """
        if not self._semaphore:
            self._semaphore = Semaphore(self.max_workers)

        if not self._lock:
            self._lock = Lock()

        # Limit the amount of running workers.
        async with self._semaphore:

            process = None
            if context is None:
                context = 0
            try:
                example_limits = WorkerResourceLimits(max_memory_bytes=Bytes(300, ByteSize.MiB),
                                                      max_cpu_time_seconds_per_call=10)  # TODO
                process = WorkerProcess(package, lms, context, example_limits)

                # Ensure FIFO.
                async with self._lock:
                    # Wait for RAM to be available.
                    await self._wait_for_memory()

                self._processes.append(process)
                await process.start()

                worker = Worker(process)

                yield worker
            finally:
                if process:
                    await process.stop(10)
                    self._processes.remove(process)
