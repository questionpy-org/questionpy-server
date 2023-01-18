from asyncio import Semaphore, Condition
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from questionpy_common.manifest import Manifest
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.misc import Size, SizeUnit
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
        self._condition: Optional[Condition] = None

        self._total_memory = 0

    def memory_available(self, size: int) -> bool:
        return self._total_memory + size <= self.max_memory

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

        if not self._condition:
            self._condition = Condition()

        # Limit the amount of running workers.
        async with self._semaphore:

            process = None
            if context is None:
                context = 0
            try:
                limits = WorkerResourceLimits(max_memory=Size(200, SizeUnit.MiB),
                                              max_cpu_time_seconds_per_call=10)  # TODO

                # Wait until there is enough memory available.
                async with self._condition:
                    await self._condition.wait_for(lambda: self.memory_available(limits.max_memory))
                    # Reserve memory for the new worker.
                    self._total_memory += limits.max_memory

                process = WorkerProcess(package, lms, context, limits)
                await process.start()

                worker = Worker(process)

                yield worker
            finally:
                if process:
                    await process.stop(10)

                # Free reserved memory and notify waiters.
                self._total_memory -= limits.max_memory
                async with self._condition:
                    self._condition.notify_all()
