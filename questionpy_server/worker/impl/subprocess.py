#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
import logging
import math
import sys
from asyncio import StreamReader
from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

import psutil
from pydantic import ByteSize

from questionpy_common.constants import KiB
from questionpy_common.environment import WorkerResourceLimits
from questionpy_server.worker import WorkerResources
from questionpy_server.worker.connection import ServerToWorkerConnection
from questionpy_server.worker.exception import WorkerNotRunningError, WorkerStartError
from questionpy_server.worker.impl._base import BaseWorker, LimitTimeUsageMixin
from questionpy_server.worker.runtime.messages import MessageToServer, MessageToWorker
from questionpy_server.worker.runtime.package_location import PackageLocation

if TYPE_CHECKING:
    from asyncio.subprocess import Process

log = logging.getLogger(__name__)
_T = TypeVar("_T", bound=MessageToServer)


class _StderrBuffer:
    """Size-limited buffer for untrusted worker output."""

    def __init__(self, stderr: StreamReader):
        self._stderr = stderr
        self._buffer = bytearray()
        self._max_size = 5 * KiB
        self._skipped_bytes = 0

    async def read_stderr(self) -> None:
        """Read and save data written by the worker to stderr (worker is set up to redirect stdout to stderr).

        Only read up to a certain amount due to security reasons and stderr should not be used besides debugging.
        """
        while True:
            space_left = self._max_size - len(self._buffer)
            if space_left == 0:
                break
            data = await self._stderr.read(space_left)
            if not data:
                return
            self._buffer.extend(data)

        # Skip all the remaining data in stderr.
        while True:
            data = await self._stderr.read(512 * KiB)
            if not data:
                return
            self._skipped_bytes += len(data)

    def flush(self) -> None:
        """Reset the stderr buffer and log the current data."""
        if self._buffer and log.isEnabledFor(logging.DEBUG):
            msg = "Worker wrote following data to stdout/stderr."
            if self._skipped_bytes:
                msg += f" (Additional {ByteSize(self._skipped_bytes).human_readable()} were skipped.)"
            indented_data = "\n".join("\t" + line for line in self._buffer.decode(errors="replace").split("\n"))
            log.debug("%s\n%s", msg, indented_data)

        self._buffer = bytearray()
        self._skipped_bytes = 0


class SubprocessWorker(BaseWorker, LimitTimeUsageMixin):
    """Worker implementation running in a non-sandboxed subprocess."""

    _worker_type = "process"

    # Allows to use a patched runtime in tests.
    _runtime_main = ["-m", "questionpy_server.worker.runtime"]

    def __init__(self, package: PackageLocation, limits: WorkerResourceLimits | None):
        super().__init__(package=package, limits=limits)

        self._proc: Process | None = None
        self._stderr_buffer: _StderrBuffer | None = None

    async def start(self) -> None:
        """Start the worker process."""
        # Turn off the worker's __debug__ flag unless ours is set as well.
        python_flags = [] if __debug__ else ["-O"]

        self._proc = await asyncio.create_subprocess_exec(
            sys.executable,
            *python_flags,
            *self._runtime_main,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if self._proc.stdout is None or self._proc.stderr is None or self._proc.stdin is None:
            raise WorkerStartError

        self._stderr_buffer = _StderrBuffer(self._proc.stderr)
        self._connection = ServerToWorkerConnection(self._proc.stdout, self._proc.stdin)

        try:
            await self._initialize()
        finally:
            # Whether initialization was successful or not, flush the logs.
            self._stderr_buffer.flush()

    async def send_and_wait_for_response(
        self, message: MessageToWorker, expected_response_message: type[_T], timeout: float | None = None
    ) -> _T:
        try:
            if timeout is None:
                timeout = self.limits.max_cpu_time_seconds_per_call if self.limits else math.inf
            self._set_time_limit(timeout)
            return await super().send_and_wait_for_response(message, expected_response_message, timeout)
        finally:
            self._reset_time_limit()
            # Write worker's stderr to log after every exchange.
            if self._stderr_buffer:
                self._stderr_buffer.flush()

    async def get_resource_usage(self) -> WorkerResources:
        if not self._proc or self._proc.returncode is not None:
            raise WorkerNotRunningError

        psutil_proc = psutil.Process(self._proc.pid)
        return WorkerResources(
            memory=psutil_proc.memory_info().rss,
            cpu_time_since_last_call=0,
            total_cpu_time=0,
        )

    def _get_observation_tasks(self) -> Sequence[asyncio.Task]:
        if not self._proc or not self._stderr_buffer:
            raise WorkerNotRunningError

        return (
            *super()._get_observation_tasks(),
            asyncio.create_task(self._proc.wait(), name="wait for worker process"),
            asyncio.create_task(self._stderr_buffer.read_stderr(), name="receive stderr from worker"),
            asyncio.create_task(self._limit_cpu_time_usage(), name="limit cpu time usage"),
        )

    async def kill(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.kill()

            # Make sure that all resources of the subprocesses are getting cleaned.
            await self._proc.wait()

    def _get_cpu_time(self) -> float:
        if not self._proc or self._proc.returncode is not None:
            raise WorkerNotRunningError

        psutil_proc = psutil.Process(self._proc.pid)
        cpu_times = psutil_proc.cpu_times()
        return cpu_times.user + cpu_times.system
