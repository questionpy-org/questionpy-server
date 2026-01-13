#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
import contextlib
import logging
import shutil
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from os.path import commonpath, normpath
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, Unpack
from zipfile import ZipFile

from questionpy_common.api.attempt import AttemptModel, AttemptScoredModel, AttemptStartedModel
from questionpy_common.api.question import LmsPermissions
from questionpy_common.constants import DIST_DIR
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.environment import RequestInfo
from questionpy_common.manifest import Manifest, PackageFile
from questionpy_common.package_location import (
    DirPackageLocation,
    FunctionPackageLocation,
    PackageLocation,
    ZipPackageLocation,
)
from questionpy_server.models import LoadedPackage, QuestionCreated
from questionpy_server.worker import PackageFileData, Worker, WorkerArgs, WorkerState
from questionpy_server.worker.exception import (
    StaticFileSizeMismatchError,
    WorkerCPUTimeLimitExceededError,
    WorkerNotRunningError,
    WorkerRealTimeLimitExceededError,
    WorkerStartError,
    WorkerStoppedError,
)
from questionpy_server.worker.runtime.messages import (
    BaseWorkerError,
    CreateQuestionFromOptions,
    Exit,
    GetOptionsForm,
    GetQPyPackageManifest,
    InitWorker,
    LoadQPyPackage,
    MessageIds,
    MessageToServer,
    MessageToWorker,
    ScoreAttempt,
    StartAttempt,
    ViewAttempt,
    WorkerError,
)

if TYPE_CHECKING:
    from questionpy_server.worker.connection import ServerToWorkerConnection

log = logging.getLogger(__name__)
_M = TypeVar("_M", bound=MessageToServer)


def _check_static_file_size(path: str, expected_size: int, real_size: int) -> None:
    if expected_size != real_size:
        msg = (
            f"Static file '{path}' has different file size on disk ('{real_size}') than in manifest ('{expected_size}')"
        )
        log.info(msg)
        raise StaticFileSizeMismatchError(msg)


def _rmtree_if_exists_sync(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


class BaseWorker(Worker, ABC):
    """Base class implementing some common functionality of workers."""

    _worker_type = "unknown"
    _init_worker_timeout = 2

    def __init__(self, **kwargs: Unpack[WorkerArgs]) -> None:
        super().__init__(**kwargs)

        self._observe_task: asyncio.Task | None = None

        self._connection: ServerToWorkerConnection | None = None
        self._expected_incoming_messages: list[tuple[MessageIds, asyncio.Future]] = []
        self._exception: BaseException | None = None

    async def _initialize(self) -> None:
        """Initializes an already running worker and starts the observe task.

        Should be called by subclasses in :meth:`start` after they have started the worker itself.
        """
        self.state = WorkerState.IDLE
        self._observe_task = asyncio.create_task(self._observe(), name="observe worker task")

        try:
            await self.send_and_wait_for_response(
                InitWorker(permissions=self.permissions, worker_type=self._worker_type, worker_home=self.worker_home),
                InitWorker.Response,
                self._init_worker_timeout,
            )

            await self._load_package(self.package, main=True)
        except BaseWorkerError as e:
            await self.stop(3)
            msg = "Worker has exited before or during initialization."
            raise WorkerStartError(msg, temporary=e.temporary, worker_name=self.name) from e

    async def _load_package(self, package_location: PackageLocation, *, main: bool) -> None:
        loaded = await self.send_and_wait_for_response(
            LoadQPyPackage(location=package_location, main=main, dependencies=self._dependencies),
            LoadQPyPackage.Response,
            self.permissions.bootstrap_timeout,
        )

        root_package_hash = package_location.hash if isinstance(package_location, ZipPackageLocation) else None
        for newly_loaded_nssn in loaded.loaded_packages:
            loaded_package = LoadedPackage(
                namespace=newly_loaded_nssn.namespace,
                short_name=newly_loaded_nssn.short_name,
                hash=root_package_hash if newly_loaded_nssn == loaded.root_nssn else None,
            )

            self.loaded_packages.append(loaded_package)

    def send(self, message: MessageToWorker) -> None:
        if self._connection is None or self._observe_task is None or self._observe_task.done():
            raise WorkerNotRunningError(temporary=True, worker_name=self.name)
        self._connection.send_message(message)

    async def send_and_wait_for_response(
        self, message: MessageToWorker, expected_response_message: type[_M], timeout: float | None = None
    ) -> _M:
        self.send(message)
        fut = asyncio.get_running_loop().create_future()
        self._expected_incoming_messages.append((expected_response_message.message_id, fut))
        self.state = WorkerState.SERVER_AWAITS_RESPONSE
        try:
            result = await fut
        except WorkerStoppedError:
            self.state = WorkerState.NOT_RUNNING
            raise
        finally:
            if self.state != WorkerState.NOT_RUNNING:
                self.state = WorkerState.IDLE
        return result

    async def _receive_messages(self) -> None:
        """Executed as a task, receives and dispatches incoming messages."""
        if self._connection is None:
            raise WorkerNotRunningError(worker_name=self.name)

        try:
            async for message in self._connection:
                if isinstance(message, WorkerError):
                    cause_id = message.expected_response_id
                    exception = message.to_exception(worker_name=self.name)
                    for future in [
                        fut for expected_id, fut in self._expected_incoming_messages if expected_id == cause_id
                    ]:
                        future.set_exception(exception)
                        self._expected_incoming_messages.remove((cause_id, future))
                else:
                    cur_id = message.message_id
                    for future in [
                        fut for expected_id, fut in self._expected_incoming_messages if expected_id == cur_id
                    ]:
                        future.set_result(message)
                        self._expected_incoming_messages.remove((cur_id, future))
        finally:
            for _, future in self._expected_incoming_messages:
                if not future.done():
                    exc = self._exception or WorkerNotRunningError(worker_name=self.name)
                    future.set_exception(exc)
            self._expected_incoming_messages = []

    def _get_observation_tasks(self) -> Sequence[asyncio.Task]:
        """Get (and possible create) all the tasks which should be observed by _observe.

        When any of these tasks exits, the worker will be killed and all other tasks will be cancelled before _observe
        exists.
        """
        return [
            asyncio.create_task(self._receive_messages(), name=f"worker-{self.name}/receive messages from worker"),
        ]

    async def _observe(self) -> None:
        """Observes the tasks returned by _get_observation_tasks."""
        pending: set[asyncio.Task] = set()
        try:
            tasks = self._get_observation_tasks()
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                with contextlib.suppress(asyncio.CancelledError):
                    if exc := task.exception():
                        self._exception = exc
        finally:
            await self.kill()

            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            self.state = WorkerState.NOT_RUNNING

            # Security: rmtree deletes symlinks to dirs without recursing into them, so there should be no danger
            # of a malicious package causing us to delete anything outside the worker home.
            await asyncio.to_thread(lambda: _rmtree_if_exists_sync(self.worker_home))

    async def stop(self, timeout: float) -> None:
        # If these are exceptions raised, either the worker is already dead, in which case we're happy, or it's somehow
        # broken, in which case we'll kill it below.
        with contextlib.suppress(BaseWorkerError, ConnectionError):
            self.send(Exit())

        if self._observe_task and not self._observe_task.done():
            try:
                # wait_for cancels the Observe task when the timeout occurs. The task will kill the process.
                await asyncio.wait_for(self._observe_task, timeout)
            except TimeoutError:
                log.info("Worker was killed because it did not stop gracefully")

    async def get_manifest(self) -> Manifest:
        ret = await self.send_and_wait_for_response(GetQPyPackageManifest(), GetQPyPackageManifest.Response)
        return ret.manifest

    async def get_options_form(
        self, request_info: RequestInfo, question_state: str | None
    ) -> tuple[OptionsFormDefinition, dict[str, object]]:
        msg = GetOptionsForm(question_state=question_state, request_info=request_info)
        ret = await self.send_and_wait_for_response(msg, GetOptionsForm.Response)
        return ret.definition, ret.form_data

    async def create_question_from_options(
        self,
        request_info: RequestInfo,
        old_state: str | None,
        form_data: dict[str, object],
        lms_permissions: LmsPermissions | None,
    ) -> QuestionCreated:
        msg = CreateQuestionFromOptions(question_state=old_state, form_data=form_data, request_info=request_info)
        ret = await self.send_and_wait_for_response(msg, CreateQuestionFromOptions.Response)

        return QuestionCreated(
            question_state=ret.question_state, lms_permissions=lms_permissions, **ret.question_model.model_dump()
        )

    async def start_attempt(self, request_info: RequestInfo, question_state: str, variant: int) -> AttemptStartedModel:
        msg = StartAttempt(question_state=question_state, variant=variant, request_info=request_info)
        ret = await self.send_and_wait_for_response(msg, StartAttempt.Response)
        return ret.attempt_started_model

    async def get_attempt(
        self,
        *,
        request_info: RequestInfo,
        question_state: str,
        attempt_state: str,
        scoring_state: str | None = None,
        response: dict | None = None,
    ) -> AttemptModel:
        msg = ViewAttempt(
            question_state=question_state,
            attempt_state=attempt_state,
            scoring_state=scoring_state,
            response=response,
            request_info=request_info,
        )
        ret = await self.send_and_wait_for_response(msg, ViewAttempt.Response)

        return ret.attempt_model

    async def score_attempt(
        self,
        *,
        request_info: RequestInfo,
        question_state: str,
        attempt_state: str,
        scoring_state: str | None = None,
        response: dict,
    ) -> AttemptScoredModel:
        msg = ScoreAttempt(
            question_state=question_state,
            attempt_state=attempt_state,
            scoring_state=scoring_state,
            response=response,
            request_info=request_info,
        )
        ret = await self.send_and_wait_for_response(msg, ScoreAttempt.Response)

        return ret.attempt_scored_model

    def _get_static_file_sync(self, path: str, manifest: Manifest) -> PackageFileData:
        path = path.lstrip("/")

        try:
            manifest_entry = manifest.static_files[path]
        except KeyError as e:
            log.info("Static file '%s' is not listed in package manifest.", path)
            raise FileNotFoundError(path) from e

        if isinstance(self.package, ZipPackageLocation):
            with ZipFile(self.package.path) as zip_file:
                dist_path = f"{DIST_DIR}/{path}"
                if commonpath((DIST_DIR, normpath(dist_path))) != DIST_DIR:
                    # This isn't strictly necessary from a security perspective, since we only look inside the ZIP.
                    # We'll still check it for consistency with dir packages.
                    log.info("Refusing to serve static file '%s', which lies outside the dist dir", path)
                    raise FileNotFoundError(path)

                try:
                    zipinfo = zip_file.getinfo(dist_path)
                except KeyError as e:
                    log.info("Static file '%s' is missing despite being listed in the manifest.", path)
                    raise FileNotFoundError(path) from e

                _check_static_file_size(path, manifest_entry.size, zipinfo.file_size)
                return PackageFileData(zipinfo.file_size, manifest_entry.mime_type, zip_file.read(dist_path))

        elif isinstance(self.package, DirPackageLocation):
            full_path: Path = (self.package.path / path).resolve()

            if not full_path.is_relative_to(self.package.path):
                log.info(
                    "Refusing to serve static file '%s', which lies outside the dist dir (resolves to '%s')",
                    path,
                    full_path,
                )
                raise FileNotFoundError(path)

            try:
                real_size = full_path.stat().st_size
            except FileNotFoundError:
                log.info("Static file '%s' is missing despite being listed in the manifest.", path)
                raise

            _check_static_file_size(path, manifest_entry.size, real_size)
            return PackageFileData(real_size, manifest_entry.mime_type, full_path.read_bytes())

        elif isinstance(self.package, FunctionPackageLocation):
            msg = "Function-based packages don't serve static files."
            raise NotImplementedError(msg)

        else:
            raise TypeError(type(self.package).__name__)

    async def get_static_file(self, path: str) -> PackageFileData:
        # TODO: Read the file inside the worker and return it in a message.
        manifest = await self.get_manifest()
        return await asyncio.to_thread(lambda: self._get_static_file_sync(path, manifest))

    async def get_static_file_index(self) -> dict[str, PackageFile]:
        return (await self.get_manifest()).static_files

    def get_loaded_packages(self, *, only_with_hash: bool = True) -> list[LoadedPackage]:
        return [p for p in self.loaded_packages if p.hash is not None or not only_with_hash]

    def __del__(self) -> None:
        if self.state != WorkerState.NOT_RUNNING:
            log.warning("Worker '%s' was not stopped correctly.", self.name)


class LimitTimeUsageMixin(Worker, ABC):
    """Implements a CPU and real time usage limit for a worker.

    _limit_cpu_time_usage needs to be added to the return value of :meth:`BaseWorker._get_observation_tasks`.
    The worker will be killed when the CPU time limit is exceeded or the worker took more than three times
    the cpu limit in real time.
    """

    _real_time_limit_factor = 1000

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cur_cpu_time_limit: float = 0
        self._request_started_cpu_time: float | None = None
        self._request_started_time: float | None = None
        self._request_started_event = asyncio.Event()

    @abstractmethod
    def _get_cpu_time(self) -> float:
        """Get worker's current CPU time (user and system time).

        Returns:
            CPU time in seconds
        """

    def _set_time_limit(self, limit: float) -> None:
        """Set a CPU and real time limit.

        The real time limit is the CPU time limit * :meth:`LimitTimeUsageMixin._real_time_limit_factor`.

        Args:
            limit: CPU time limit in seconds
        """
        self._cur_cpu_time_limit = limit
        self._request_started_cpu_time = self._get_cpu_time()
        self._request_started_time = time.time()
        self._request_started_event.set()

    def _reset_time_limit(self) -> None:
        self._cur_cpu_time_limit = 0
        self._request_started_cpu_time = None
        self._request_started_time = None
        self._request_started_event.clear()

    async def _limit_cpu_time_usage(self) -> None:
        """Ensures that the worker will be killed when it is taking too much time. Executed as a task."""
        while True:
            await self._request_started_event.wait()

            # CPU-time is always less or equal to real time (when single-threaded).
            await asyncio.sleep(self._cur_cpu_time_limit)

            # Check if the start time is still set. Probably the request was already processed or
            # maybe another request started meanwhile.
            while self._request_started_cpu_time is not None and self._request_started_time is not None:
                remaining_cpu_time = self._request_started_cpu_time + self._cur_cpu_time_limit - self._get_cpu_time()
                if remaining_cpu_time <= 0:
                    raise WorkerCPUTimeLimitExceededError(self._cur_cpu_time_limit, worker_name=self.name)

                remaining_time = (
                    self._request_started_time + (self._cur_cpu_time_limit * self._real_time_limit_factor) - time.time()
                )
                if remaining_time <= 0:
                    raise WorkerRealTimeLimitExceededError(
                        self._cur_cpu_time_limit * self._real_time_limit_factor, worker_name=self.name
                    )

                await asyncio.sleep(max(min(remaining_cpu_time, remaining_time), 0.05))
