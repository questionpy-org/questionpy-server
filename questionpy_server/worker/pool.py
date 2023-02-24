from asyncio import Semaphore, Condition
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Type

from questionpy_common.constants import MiB

from . import WorkerResourceLimits
from .exception import WorkerStartError
from .worker import Worker
from .worker.subprocess import SubprocessWorker


class WorkerPool:
    def __init__(self, max_workers: int, max_memory: int,
                 worker_type: Type[Worker] = SubprocessWorker):
        """
        Initialize the worker pool.

        :param max_workers: maximum number of workers being executed in parallel
        :param max_memory: maximum memory (in bytes) that all workers in the pool are allowed to consume
        :param worker_type: worker implementation
        """
        self.max_workers = max_workers
        self.max_memory = max_memory

        self._worker_type = worker_type

        self._semaphore: Optional[Semaphore] = None
        self._condition: Optional[Condition] = None

        self._total_memory = 0

    def memory_available(self, size: int) -> bool:
        return self._total_memory + size <= self.max_memory

    @asynccontextmanager
    async def get_worker(self, package: Path, _lms: int, _context: Optional[int]) -> AsyncIterator[Worker]:
        """
        Get a (new) worker executing a QuestionPy package. A context manager is used to ensure
        that a worker is always given back to the pool.

        :param package: path to QuestionPy package
        :param _lms: id of the LMS
        :param _context: context id within the lms
        :return: a worker
        """
        if not self._semaphore:
            self._semaphore = Semaphore(self.max_workers)

        if not self._condition:
            self._condition = Condition()

        # Limit the amount of running workers.
        async with self._semaphore:
            worker = None
            reserved_memory = False
            try:
                limits = WorkerResourceLimits(max_memory=200 * MiB,
                                              max_cpu_time_seconds_per_call=10)  # TODO
                if self.max_memory < limits.max_memory:
                    raise WorkerStartError("The worker needs more memory than available.")

                # Wait until there is enough memory available.
                async with self._condition:
                    await self._condition.wait_for(lambda: self.memory_available(limits.max_memory))
                    # Reserve memory for the new worker.
                    self._total_memory += limits.max_memory
                    reserved_memory = True

                worker = self._worker_type(package, limits)
                await worker.start()

                yield worker
            finally:
                if worker:
                    await worker.stop(10)

                if reserved_memory:
                    # Free reserved memory and notify waiters.
                    self._total_memory -= limits.max_memory
                    async with self._condition:
                        self._condition.notify_all()
