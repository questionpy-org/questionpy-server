#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
import contextlib
import logging
from abc import ABC
from collections.abc import Sequence
from typing import TypeVar

from questionpy_common.api.attempt import AttemptModel, AttemptScoredModel
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.environment import RequestUser, WorkerResourceLimits
from questionpy_server.api.models import AttemptStarted, QuestionCreated
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.worker.connection import ServerToWorkerConnection
from questionpy_server.worker.exception import WorkerNotRunningError, WorkerStartError
from questionpy_server.worker.runtime.messages import (
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
from questionpy_server.worker.runtime.package_location import PackageLocation
from questionpy_server.worker.worker import Worker, WorkerState

log = logging.getLogger(__name__)
_T = TypeVar("_T", bound=MessageToServer)


class BaseWorker(Worker, ABC):
    """Base class implementing some common functionality of workers."""

    _worker_type = "unknown"

    def __init__(self, package: PackageLocation, limits: WorkerResourceLimits | None) -> None:
        super().__init__(package, limits)

        self._observe_task: asyncio.Task | None = None

        self._connection: ServerToWorkerConnection | None = None
        self._expected_incoming_messages: list[tuple[MessageIds, asyncio.Future]] = []

    async def _initialize(self) -> None:
        """Initializes an already running worker and starts the observe task.

        Should be called by subclasses in :meth:`start` after they have started the worker itself.
        """
        self.state = WorkerState.IDLE
        self._observe_task = asyncio.create_task(self._observe(), name="observe worker task")

        try:
            await self._send_and_wait_response(
                InitWorker(
                    limits=self.limits,
                    worker_type=self._worker_type,
                ),
                InitWorker.Response,
            )
            await self._send_and_wait_response(
                LoadQPyPackage(location=self.package, main=True), LoadQPyPackage.Response
            )
        except WorkerNotRunningError as e:
            raise WorkerStartError("Worker has exited before or during initialization.") from e

    def send(self, message: MessageToWorker) -> None:
        if self._connection is None or self._observe_task is None or self._observe_task.done():
            raise WorkerNotRunningError()
        self._connection.send_message(message)

    async def _send_and_wait_response(self, message: MessageToWorker, expected_response_message: type[_T]) -> _T:
        self.send(message)
        fut = asyncio.get_running_loop().create_future()
        self._expected_incoming_messages.append((expected_response_message.message_id, fut))
        self.state = WorkerState.SERVER_AWAITS_RESPONSE
        result = await fut
        self.state = WorkerState.IDLE
        return result

    async def _receive_messages(self) -> None:
        """Executed as a task, receives and dispatches incoming messages."""
        if self._connection is None:
            raise WorkerNotRunningError()

        try:
            async for message in self._connection:
                if isinstance(message, WorkerError):
                    cause_id = message.expected_response_id
                    exception = message.to_exception()
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
                    future.set_exception(WorkerNotRunningError())
            self._expected_incoming_messages = []

    def _get_observation_tasks(self) -> Sequence[asyncio.Task]:
        """Get (and possible create) all the tasks which should be observed by _observe.

        When any of these tasks exits, the worker will be killed and all other tasks will be cancelled before _observe
        exists.
        """
        return [
            asyncio.create_task(self._receive_messages(), name="receive messages from worker"),
        ]

    async def _observe(self) -> None:
        """Observes the tasks returned by _get_observation_tasks."""
        pending: Sequence[asyncio.Task] = []
        try:
            tasks = self._get_observation_tasks()
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            self.state = WorkerState.NOT_RUNNING

            await self.kill()

            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def stop(self, timeout: float) -> None:
        try:
            self.send(Exit())
        except WorkerNotRunningError:
            # No need to stop it then.
            return

        if self._observe_task and not self._observe_task.done():
            try:
                # wait_for cancels the Observe task when the timeout occurs. The task will kill the process.
                await asyncio.wait_for(self._observe_task, timeout)
            except TimeoutError:
                log.info("Worker was killed because it did not stop gracefully")

    async def get_manifest(self) -> ComparableManifest:
        msg = GetQPyPackageManifest(path=str(self.package))
        ret = await self._send_and_wait_response(msg, GetQPyPackageManifest.Response)
        return ComparableManifest(**ret.manifest.model_dump())

    async def get_options_form(
        self, request_user: RequestUser, question_state: str | None
    ) -> tuple[OptionsFormDefinition, dict[str, object]]:
        msg = GetOptionsForm(question_state=question_state, request_user=request_user)
        ret = await self._send_and_wait_response(msg, GetOptionsForm.Response)
        return ret.definition, ret.form_data

    async def create_question_from_options(
        self, request_user: RequestUser, old_state: str | None, form_data: dict[str, object]
    ) -> QuestionCreated:
        msg = CreateQuestionFromOptions(question_state=old_state, form_data=form_data, request_user=request_user)
        ret = await self._send_and_wait_response(msg, CreateQuestionFromOptions.Response)

        return QuestionCreated(question_state=ret.question_state, **ret.question_model.model_dump())

    async def start_attempt(self, request_user: RequestUser, question_state: str, variant: int) -> AttemptStarted:
        msg = StartAttempt(question_state=question_state, variant=variant, request_user=request_user)
        ret = await self._send_and_wait_response(msg, StartAttempt.Response)

        return AttemptStarted(attempt_state=ret.attempt_state, **ret.attempt_model.model_dump())

    async def get_attempt(
        self,
        *,
        request_user: RequestUser,
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
            request_user=request_user,
        )
        ret = await self._send_and_wait_response(msg, ViewAttempt.Response)

        return ret.attempt_model

    async def score_attempt(
        self,
        *,
        request_user: RequestUser,
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
            request_user=request_user,
        )
        ret = await self._send_and_wait_response(msg, ScoreAttempt.Response)

        return ret.attempt_scored_model
