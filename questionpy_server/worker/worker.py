import asyncio
import json
import logging
import sys
from asyncio.subprocess import Process
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Type, TypeVar
from .runtime.lib import WorkerResourceLimits, send_message
from .runtime.messages import MessageIds, messages_header_struct, MessageToServer, MessageToWorker, \
    InvalidMessageIdError, InitWorker, Exit, LoadQPyPackage


@dataclass
class WorkerResources:
    """Current resource usage."""
    memory_bytes: int
    cpu_time_since_last_call: float
    total_cpu_time: float


class WorkerState(Enum):
    NOT_RUNNING = 1
    IDLE = 2
    SERVER_AWAITS_RESPONSE = 3  # server send a message to worker and is waiting for a response
    WORKER_AWAITS_RESPONSE = 4  # worker send a request/message to server and server is now processing the request


_T = TypeVar('_T', bound=MessageToServer)  # for WorkerProcessBase.send_and_wait_response
log = logging.getLogger('worker')


class WorkerProcessBase:
    """Base class for representing a QuestionPy worker process."""
    def __init__(self, package: Path, lms: int, context: int, limits: WorkerResourceLimits):
        """
        :param package: path to QuestionPy package
        :param lms: id of the LMS
        :param context: context id within the lms
        :param limits: maximum resources a worker is allowed to consume
        """
        self.package: Path = package
        self.lms: int = lms
        self.context: int = context
        self.limits: WorkerResourceLimits = limits
        self.loaded_options: set[str] = set()

    async def start(self) -> None:
        """Start the worker process."""
        raise NotImplementedError()

    def send(self, message: MessageToWorker) -> None:
        """Send a message to the worker."""
        raise NotImplementedError()

    async def send_and_wait_response(self, message: MessageToWorker, expected_response_message: Type[_T]) -> _T:
        """Send a message to the worker and wait for a reply."""
        raise NotImplementedError()

    async def kill(self) -> None:
        """Kill the worker process."""
        raise NotImplementedError()

    def get_resource_usage(self) -> WorkerResources:
        """Get the worker's current resource usage."""
        raise NotImplementedError()


class WorkerProcess(WorkerProcessBase):
    """A worker that is executed in a new process."""

    def __init__(self, package: Path, lms: int, context: int, limits: WorkerResourceLimits):
        super().__init__(package, lms, context, limits)
        self.proc: Optional[Process] = None
        self.state: WorkerState = WorkerState.NOT_RUNNING
        self.observe_task: Optional[asyncio.Task] = None

        self._connection: Optional[ServerToWorkerConnection] = None
        self._expected_incoming_messages: list[tuple[MessageIds, asyncio.Future]] = []

        self.stderr_data: bytearray = bytearray()
        self._stderr_data_max_size: int = 5 * 1024
        self.stderr_skipped_data: int = 0
        self.ignore_errors: bool = False  # do not log errors in worker when reading from stdin

    async def start(self) -> None:
        """Start the worker process."""
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable,
            '-m', 'questionpy_server.worker.runtime',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if self.proc.stdout is None or self.proc.stderr is None or self.proc.stdin is None:
            raise WorkerStartError()

        self.state = WorkerState.IDLE
        self._connection = ServerToWorkerConnection(self.proc.stdout, self.proc.stdin)
        self.observe_task = asyncio.create_task(self.observe(), name='observe worker task')

        try:
            init_msg = InitWorker(max_memory=self.limits.max_memory_bytes,
                                  max_cpu_time=self.limits.max_cpu_time_seconds_per_call)
            await self.send_and_wait_response(init_msg, InitWorker.Response)

            load_msg = LoadQPyPackage(path=str(self.package), main=True)
            await self.send_and_wait_response(load_msg, LoadQPyPackage.Response)

        except WorkerNotRunningError:
            # Log stderr, maybe there is some information why the worker did not start.
            self.reset_stderr_data()
            raise

    def send(self, message: MessageToWorker) -> None:
        """Send a message to the worker."""
        if self._connection is None:
            raise WorkerNotRunningError()
        self._connection.send_message(message)

    async def send_and_wait_response(self, message: MessageToWorker, expected_response_message: Type[_T]) -> _T:
        """Send a message to the worker and wait for a response."""
        if self._connection is None:
            raise WorkerNotRunningError()

        fut = asyncio.get_running_loop().create_future()
        self._expected_incoming_messages.append((expected_response_message.message_id, fut))
        self._connection.send_message(message)
        self.state = WorkerState.SERVER_AWAITS_RESPONSE
        result = await fut
        self.state = WorkerState.IDLE
        self.reset_stderr_data()
        return result

    async def receive_messages(self) -> None:
        """Executed as a task, receives and dispatches incoming messages."""
        if self._connection is None:
            raise WorkerNotRunningError()

        async for message in self._connection:
            cur_id = message.message_id
            for future in [fut for expected_id, fut in self._expected_incoming_messages if expected_id == cur_id]:
                future.set_result(message)
                self._expected_incoming_messages.remove((cur_id, future))

    async def read_stderr(self) -> None:
        """
        Read and save data written by the worker to stderr (worker is set up to redirect stdout to stderr).
        Only read up to a certain amount due to security reasons and stderr should not be used besides debugging.
        """
        if self.proc is None or self.proc.stderr is None:
            return

        while True:
            space_left = self._stderr_data_max_size - len(self.stderr_data)
            if space_left == 0:
                break
            data = await self.proc.stderr.read(space_left)
            if not data:
                return
            self.stderr_data.extend(data)

        # Skip all the remaining data in stderr.
        while True:
            data = await self.proc.stderr.read(512 * 1024)
            if not data:
                return
            self.stderr_skipped_data += len(data)

    def reset_stderr_data(self, log_data: bool = True) -> None:
        """Reset the stderr buffer and optionally log the current data."""
        if log_data and self.stderr_data:
            msg = "Worker wrote following data to stdout/stderr.\n"
            msg_after = ""
            if self.stderr_skipped_data:
                msg_after += f" (additional {self.stderr_skipped_data} bytes were skipped)."
            log.warning("%s%s%s ", msg, self.stderr_data, msg_after)
        self.stderr_data = bytearray()
        self.stderr_skipped_data = 0

    async def observe(self) -> None:
        """Observes receive message and stderr tasks and that the process is still running."""
        if self._connection is None or self.proc is None:
            raise WorkerNotRunningError()

        receive_message_task = None
        read_stderr_task = None
        process_wait_task = None
        try:
            receive_message_task = asyncio.create_task(self.receive_messages(),
                                                       name="receive messages from worker")
            read_stderr_task = asyncio.create_task(self.read_stderr(), name="receive stderr from worker")
            process_wait_task = asyncio.create_task(self.proc.wait(), name="wait for worker process")
            await asyncio.wait((receive_message_task, read_stderr_task, process_wait_task),
                               return_when=asyncio.FIRST_COMPLETED)

        finally:
            self.state = WorkerState.NOT_RUNNING
            for _, future in self._expected_incoming_messages:
                future.set_exception(WorkerNotRunningError())
            self._expected_incoming_messages = []
            if self.proc.returncode is None and process_wait_task and not process_wait_task.done():
                try:
                    self.proc.kill()
                    await process_wait_task
                except ProcessLookupError:
                    pass
            if self.proc.returncode != 0 and not self.ignore_errors:
                log.warning("Worker exited with code %d", self.proc.returncode)
            if receive_message_task:
                receive_message_task.cancel()
                try:
                    await receive_message_task
                except (InvalidMessageIdError, asyncio.IncompleteReadError):
                    if not self.ignore_errors:
                        log.exception("Error while reading from worker stdin")
                except asyncio.CancelledError:
                    pass
            if read_stderr_task:
                read_stderr_task.cancel()
                self.reset_stderr_data()
                try:
                    await read_stderr_task
                except asyncio.CancelledError:
                    pass

    async def stop(self, timeout: float) -> None:
        """Try to stop the worker gracefully. When it does not stop by itself, kill it after timeout seconds."""
        self.ignore_errors = True
        self.send(Exit())  # TODO Better send a SIGTERM signal instead?
        try:
            if self.observe_task and not self.observe_task.done():
                # wait_for cancels the Observe task when the timeout occurs. The task will kill the process.
                await asyncio.wait_for(self.observe_task, timeout)
        except asyncio.TimeoutError:
            log.info("Worker was killed because it did not stop gracefully")

    async def kill(self) -> None:
        """Kill the worker process."""
        self.ignore_errors = True
        if self.proc and self.proc.returncode is None:
            self.proc.kill()


class SandboxProcess(WorkerProcess):
    """A worker that is executed in a sandbox."""


class SameProcess(WorkerProcessBase):
    """Do not spawn a new process for this worker (might be used by questionpy-sdk)."""


class ServerToWorkerConnection(AsyncIterator[MessageToServer]):
    """Controls the connection (stdin/stdout pipes) from the server to a worker."""

    def __init__(self, stream_in: asyncio.StreamReader, stream_out: asyncio.StreamWriter):
        self.stream_in: asyncio.StreamReader = stream_in
        self.stream_out: asyncio.StreamWriter = stream_out
        self.stream_in_invalid_state: bool = False

    def send_message(self, message: MessageToWorker) -> None:
        """Send a message to a worker."""
        send_message(message, self.stream_out)

    async def receive_message(self) -> MessageToServer:
        """Receive a message from a worker."""
        if self.stream_in_invalid_state:
            raise ConnectionError()

        header_bytes = await self.stream_in.readexactly(messages_header_struct.size)
        message_id, length = messages_header_struct.unpack(header_bytes)
        message_type = MessageToServer.types.get(message_id, None)
        if message_type is None:
            self.stream_in_invalid_state = True
            raise InvalidMessageIdError(message_id, length)

        if length:
            json_data = await self.stream_in.readexactly(length)
            json_obj = json.loads(json_data)
            return message_type.parse_obj(json_obj)

        return message_type()

    def __aiter__(self) -> AsyncIterator[MessageToServer]:
        return self

    async def __anext__(self) -> MessageToServer:
        return await self.receive_message()


class WorkerNotRunningError(Exception):
    pass


class WorkerStartError(Exception):
    pass
