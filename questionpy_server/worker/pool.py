#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from asyncio import Condition, Semaphore
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from questionpy_common.constants import MiB
from questionpy_common.environment import WorkerResourceLimits
from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.runtime.package_location import PackageLocation

from . import Worker
from .exception import WorkerStartError


class WorkerPool:
    def __init__(self, max_workers: int, max_memory: int, worker_type: type[Worker] = SubprocessWorker):
        """Initialize the worker pool.

        Args:
            max_workers (int): maximum number of workers being executed in parallel
            max_memory (int): maximum memory (in bytes) that all workers in the pool are allowed to consume
            worker_type (type[Worker]): worker implementation
        """
        self.max_workers = max_workers
        self.max_memory = max_memory

        self._worker_type = worker_type

        self._semaphore: Semaphore | None = None
        self._condition: Condition | None = None

        self._running_workers: int = 0
        self._requests: int = 0

        self._total_memory = 0

    def memory_available(self, size: int) -> bool:
        return self._total_memory + size <= self.max_memory

    @asynccontextmanager
    async def get_worker(self, package: PackageLocation, _lms: int, _context: int | None) -> AsyncIterator[Worker]:
        """Get a (new) worker executing a QuestionPy package.

        A context manager is used to ensure that a worker is always given back to the pool.

        Args:
            package: path to QuestionPy package
            _lms: id of the LMS
            _context: context id within the lms

        Returns:
            A worker
        """
        if not self._semaphore:
            self._semaphore = Semaphore(self.max_workers)

        if not self._condition:
            self._condition = Condition()

        self._requests += 1

        # Limit the amount of running workers.
        async with self._semaphore:
            self._running_workers += 1

            worker = None
            reserved_memory = False
            try:
                limits = WorkerResourceLimits(max_memory=200 * MiB, max_cpu_time_seconds_per_call=10)
                if self.max_memory < limits.max_memory:
                    msg = "The worker needs more memory than available."
                    raise WorkerStartError(msg)

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

                self._running_workers -= 1
                self._requests -= 1

    async def get_requests_in_process(self) -> int:
        """Get the number of workers currently running.

        Returns:
            int: The count of workers currently running.
        """
        return self._running_workers

    async def get_requests_in_queue(self) -> int:
        """Get the number of pending requests.

        Returns:
            int: The count of pending requests.
        """
        return self._requests - self._running_workers
