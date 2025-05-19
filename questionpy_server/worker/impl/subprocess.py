#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
import logging
import math
import re
import signal
import sys
from asyncio import StreamReader
from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar, Unpack

import psutil
from pydantic import ByteSize

from questionpy_common.constants import KiB
from questionpy_server.worker import WorkerArgs, WorkerResources
from questionpy_server.worker.connection import ServerToWorkerConnection
from questionpy_server.worker.exception import (
    WorkerCPUTimeLimitExceededError,
    WorkerNotRunningError,
    WorkerRealTimeLimitExceededError,
    WorkerStartError,
)
from questionpy_server.worker.impl._base import BaseWorker, LimitTimeUsageMixin
from questionpy_server.worker.runtime.messages import MessageToServer, MessageToWorker

if TYPE_CHECKING:
    from asyncio.subprocess import Process

log = logging.getLogger(__name__)
_T = TypeVar("_T", bound=MessageToServer)


class _StderrBuffer:
    """Size-limited buffer for untrusted worker output."""

    _control_char_pattern = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")
    """A regex pattern to match all control characters except newline."""

    def __init__(self, worker_name: str, stderr: StreamReader):
        self._worker_name = worker_name
        self._stderr = stderr
        self._buffer = bytearray()
        self._max_size = 5 * KiB
        self._skipped_bytes = 0

    @classmethod
    def _remove_ascii_control_characters(cls, data: str) -> str:
        """Replace ASCII control characters with their hex representation and remove newline/whitespaces at the end."""
        return cls._control_char_pattern.sub(lambda m: f"\\x{ord(m.group()):02x}", data).rstrip()

    async def read_stderr(self) -> None:
        """Read and save data written by the worker to stderr (worker is set up to redirect stdout to stderr).

        Normally, data is only read up to a certain amount for security reasons and stderr should not be used
        besides debugging. If debug log level is enabled, read stderr line by line and log all data immediately.

        ASCII control characters are replaced, especially the escape character and ANSI escape codes should have
        no effect.
        """
        if log.isEnabledFor(logging.DEBUG):
            while line := await self._stderr.readline():
                cleaned = self._remove_ascii_control_characters(line.decode(errors="replace"))
                log.debug("Worker %s output: %s", self._worker_name, cleaned)
            return

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
        if self._buffer and log.isEnabledFor(logging.INFO):
            skipped_bytes_msg = ""
            if self._skipped_bytes:
                skipped_bytes_msg = f"\n\t  (additional {ByteSize(self._skipped_bytes).human_readable()} were skipped)"
            indented_data = "\n".join(
                "\t" + self._remove_ascii_control_characters(line)
                for line in self._buffer.decode(errors="replace").split("\n")
            )
            log.info(
                "Worker %s wrote following data to stdout/stderr:\n%s%s",
                self._worker_name,
                indented_data,
                skipped_bytes_msg,
            )

        self._buffer = bytearray()
        self._skipped_bytes = 0


class SubprocessWorker(BaseWorker, LimitTimeUsageMixin):
    """Worker implementation running in a non-sandboxed subprocess."""

    _worker_type = "process"

    # Allows to use a patched runtime in tests.
    _runtime_main = ["-m", "questionpy_server.worker.runtime"]

    def __init__(self, **kwargs: Unpack[WorkerArgs]):
        super().__init__(**kwargs)

        self._proc: Process | None = None
        self._stderr_buffer: _StderrBuffer | None = None

    async def start(self) -> None:
        """Start the worker process."""
        # Turn off the worker's __debug__ flag unless ours is set as well.
        python_flags = [] if __debug__ else ["-O"]

        env = {
            # OpenBLAS is used by NumPy and creates a number of threads on import.
            # Each thread allocates a bunch of virtual memory, so more than 2 threads breaks the default memory limit.
            # By default, the number of threads is proportional to the available CPUs.
            "OPENBLAS_NUM_THREADS": "2"
        }

        self._proc = await asyncio.create_subprocess_exec(
            sys.executable,
            *python_flags,
            *self._runtime_main,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self.worker_home,
            start_new_session=True,
        )

        if self._proc.stdout is None or self._proc.stderr is None or self._proc.stdin is None:
            msg = "Could not start the worker process."
            raise WorkerStartError(msg, worker_name=self.name)

        self._stderr_buffer = _StderrBuffer(self.name, self._proc.stderr)
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
            raise WorkerNotRunningError(worker_name=self.name)

        psutil_proc = psutil.Process(self._proc.pid)
        return WorkerResources(
            memory=psutil_proc.memory_info().rss,
            cpu_time_since_last_call=0,
            total_cpu_time=0,
        )

    def _get_observation_tasks(self) -> Sequence[asyncio.Task]:
        if not self._proc or not self._stderr_buffer:
            raise WorkerNotRunningError(worker_name=self.name)

        prefix = f"worker-{self.name}/"
        return (
            *super()._get_observation_tasks(),
            asyncio.create_task(self._proc.wait(), name=f"{prefix}wait for worker process"),
            asyncio.create_task(self._stderr_buffer.read_stderr(), name=f"{prefix}receive stderr from worker"),
            asyncio.create_task(self._limit_cpu_time_usage(), name=f"{prefix}limit cpu time usage"),
        )

    async def kill(self) -> None:
        if self._proc and self._proc.returncode is None:
            if self._exception and (
                isinstance(self._exception, WorkerRealTimeLimitExceededError | WorkerCPUTimeLimitExceededError)
            ):
                # If the worker has to be killed because of a real-time or CPU-time limit, send an abort signal to the
                # worker that will make it to dump a Python traceback (thanks to the fault handler).
                self._proc.send_signal(signal.SIGABRT)

                # We give it a short time to dump the traceback. Usually, SIGABRT should terminate the process
                # right after Python's signal handler returns.
                try:
                    await asyncio.wait_for(self._proc.wait(), 0.2)
                except TimeoutError:
                    log.warning("Worker %s did not terminate after SIGABRT", self.name)
                else:
                    return

            self._proc.kill()

            # Make sure that all resources of the subprocesses are getting cleaned.
            await self._proc.wait()

    def _get_cpu_time(self) -> float:
        if not self._proc or self._proc.returncode is not None:
            raise WorkerNotRunningError(worker_name=self.name)

        psutil_proc = psutil.Process(self._proc.pid)
        cpu_times = psutil_proc.cpu_times()
        return cpu_times.user + cpu_times.system
