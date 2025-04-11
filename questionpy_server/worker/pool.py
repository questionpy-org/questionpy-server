#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import asyncio
import logging
import shutil
import tempfile
from asyncio import Condition, Lock, Semaphore
from base64 import b32hexencode
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from random import Random
from typing import NamedTuple, Self, assert_never

from pydantic import ByteSize

from questionpy_common.constants import MiB
from questionpy_common.environment import WorkerResourceLimits
from questionpy_common.error import QPyBaseError
from questionpy_server.worker.impl.subprocess import SubprocessWorker
from questionpy_server.worker.runtime.package_location import (
    DirPackageLocation,
    FunctionPackageLocation,
    PackageLocation,
    ZipPackageLocation,
)

from . import Worker, WorkerState
from .impl.thread import ThreadWorker

_log = logging.getLogger(__name__)


class _WorkerPoolMemoryError(QPyBaseError):
    """Raised when the worker pool cannot free enough memory."""

    def __init__(self) -> None:
        super().__init__("Cannot free the required amount of memory. This is likely a bug.")


def _memory_limit_or_zero(limits: WorkerResourceLimits | None) -> int:
    return limits.max_memory if limits else 0


class _IdleWorkersIdentifier(NamedTuple):
    package: PackageLocation
    lms: int
    context: int | None


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

        # TODO: Make this configurable (#137)
        self._limits_per_worker = WorkerResourceLimits(max_memory=200 * MiB, max_cpu_time_seconds_per_call=10)
        if self.max_memory < self._limits_per_worker.max_memory:
            pool_max = ByteSize(self.max_memory).human_readable()
            worker_max = ByteSize(self._limits_per_worker.max_memory).human_readable()
            msg = f"Memory limit of {worker_max} for a single worker exceeds max pool memory of {pool_max}."
            raise ValueError(msg)

        self._worker_type = worker_type

        self._lock: Lock = Lock()
        self._semaphore: Semaphore = Semaphore(self.max_workers)
        self._condition: Condition = Condition()

        self._idle_workers: dict[_IdleWorkersIdentifier, deque[Worker]] = defaultdict(deque)
        """Maps a package to a deque of workers that are currently idle and have that package loaded. The first worker
        in the deque is the most recently used one."""
        self._oldest_idle_workers: deque[tuple[Worker, _IdleWorkersIdentifier]] = deque()
        """A deque of workers that are currently idle and have a package loaded. The first worker in the deque is the
        most recently used one."""

        self._workers_requested: int = 0
        self._workers_in_use: int = 0

        self._memory_in_use = 0
        self._memory_idle = 0

        self._working_dir = Path(tempfile.mkdtemp(prefix="qpy-pool-"))
        self._random = Random()

        _log.debug(
            "Started worker pool of at most '%s' workers with '%s' memory in '%s'",
            max_workers,
            ByteSize(max_memory).human_readable(),
            self._working_dir,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop_idle_workers()

        await asyncio.to_thread(lambda: shutil.rmtree(self._working_dir))

    def _memory_available(self, required_memory: int) -> bool:
        """Checks whether the required memory to start or reuse a worker is available.

        The total memory of idle workers is not considered.
        """
        return self.max_memory - self._memory_in_use >= required_memory

    @asynccontextmanager
    async def get_worker(self, package: PackageLocation, lms: int, context: int | None) -> AsyncIterator[Worker]:
        """Get a (new) worker executing a QuestionPy package.

        A context manager is used to ensure that a worker is always given back to the pool.

        Args:
            package: path to QuestionPy package
            lms: id of the LMS
            context: context id within the lms

        Returns:
            A worker
        """
        self._workers_requested += 1

        # Limit the amount of running workers.
        async with self._semaphore:
            worker = None
            try:
                # Wait until there is enough memory available.
                # We need the additional lock, since `Condition.wait_for`/`Condition.notify` in comparison to
                # `Lock.acquire` is not explicitly documented as fair. This ensures that no starvation occurs.
                async with self._lock, self._condition:
                    await self._condition.wait_for(lambda: self._memory_available(self._limits_per_worker.max_memory))
                    worker = await self._create_or_reuse_worker(package, lms, context, self._limits_per_worker)
                    self._workers_in_use += 1

                yield worker
            finally:
                if worker:
                    async with self._condition:
                        await self._handle_idle_worker(package, lms, context, worker)
                        self._condition.notify()
                        self._workers_in_use -= 1

                self._workers_requested -= 1

    async def _stop_oldest_idle_worker(self) -> int | None:
        """Stops the oldest idle worker.

        Returns:
            The freed memory or None if there are no more idle workers to stop.
        """
        if not self._oldest_idle_workers:
            return None

        # Get the oldest worker and remove it.
        worker, identifier = self._oldest_idle_workers.pop()
        self._idle_workers[identifier].remove(worker)
        if not self._idle_workers[identifier]:
            # There are no more available workers with this package.
            del self._idle_workers[identifier]

        # Stop the worker and free the memory.
        await worker.stop(10)

        max_memory = _memory_limit_or_zero(worker.limits)
        self._memory_idle -= max_memory
        return max_memory

    async def _free_memory(self, required_memory: int) -> None:
        """Stops idle workers until the required amount of memory is available."""
        available_memory = self.max_memory - self._memory_in_use - self._memory_idle
        if available_memory >= required_memory:
            # As there is more memory available than required, we do not need to stop any idle workers.
            return

        # Stop only as many workers as needed.
        required_memory -= available_memory
        while required_memory > 0:
            freed_memory = await self._stop_oldest_idle_worker()
            if freed_memory is None:
                break
            required_memory -= freed_memory

        if required_memory > 0:
            raise _WorkerPoolMemoryError

    def _generate_worker_name(self, package: PackageLocation, lms: int, context: int | None) -> str:
        if isinstance(package, ZipPackageLocation):
            package_part = package.hash[:10]
        elif isinstance(package, DirPackageLocation):
            package_part = "dir"
        elif isinstance(package, FunctionPackageLocation):
            package_part = "fun"
        else:
            assert_never(package)

        random_part = b32hexencode(self._random.randbytes(5)).lower().decode("ascii")
        # TODO: Collisions should be pretty unlikely, but we should still ensure no worker with the same name is
        #  currently running. That would require us to store all running workers though.
        return f"{package_part}-{lms}-{'N' if context is None else context}-{random_part}"

    async def _create_or_reuse_worker(
        self, package: PackageLocation, lms: int, context: int | None, limits: WorkerResourceLimits
    ) -> Worker:
        """If possible, get an idle worker or create a new one."""
        identifier = _IdleWorkersIdentifier(package, lms, context)
        if identifier in self._idle_workers:
            # There is an idle worker with this package loaded - reuse the most recent one.
            worker = self._idle_workers[identifier].popleft()
            if not self._idle_workers[identifier]:
                # There are no more available workers with this package.
                del self._idle_workers[identifier]
            self._oldest_idle_workers.remove((worker, identifier))

            self._memory_idle -= _memory_limit_or_zero(worker.limits)
        else:
            # We need to create a new worker - free as much memory as needed to start the worker.
            await self._free_memory(limits.max_memory)

            name = self._generate_worker_name(package, lms, context)
            worker_home = self._working_dir / f"worker-{name}"
            worker_home.mkdir()
            worker = self._worker_type(name=name, package=package, limits=limits, worker_home=worker_home)
            await worker.start()

        # Reserve the memory.
        self._memory_in_use += limits.max_memory if self._worker_type is not ThreadWorker else 0

        return worker

    async def _handle_idle_worker(
        self, package: PackageLocation, lms: int, context: int | None, worker: Worker
    ) -> None:
        """Adds a worker to the pool of reusable workers."""
        # Free reserved memory.
        self._memory_in_use -= _memory_limit_or_zero(worker.limits)

        # Check if the worker is idling.
        if worker.state == WorkerState.IDLE:
            # Free as much memory as need to store the idle worker.
            required_memory = _memory_limit_or_zero(worker.limits)
            await self._free_memory(required_memory)

            # Add the worker.
            identifier = _IdleWorkersIdentifier(package, lms, context)
            self._idle_workers[identifier].appendleft(worker)
            self._oldest_idle_workers.appendleft((worker, identifier))

            self._memory_idle += _memory_limit_or_zero(worker.limits)
        else:
            # We cannot reuse this worker as it is not idling.
            await worker.stop(10)

    async def stop_idle_workers(self) -> None:
        """Stops all idle workers gracefully."""
        async with self._condition:
            while await self._stop_oldest_idle_worker() is not None:
                continue

    def get_workers_in_use_count(self) -> int:
        """Get the number of workers currently running but not idle."""
        return self._workers_in_use

    def get_pending_worker_request_count(self) -> int:
        """Get the number of pending worker requests."""
        return self._workers_requested - self._workers_in_use

    def __del__(self) -> None:
        if self._working_dir.exists() or self._idle_workers:
            _log.warning("Worker pool was not closed correctly.")
