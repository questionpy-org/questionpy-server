#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import asyncio
import contextlib
import json
import logging
from abc import ABC
from pathlib import Path
from typing import Optional, Type, TypeVar, Sequence

from questionpy_common.elements import OptionsFormDefinition

from questionpy_server.api.models import Question, ScoringMethod
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.worker import WorkerResourceLimits
from questionpy_server.worker.connection import ServerToWorkerConnection
from questionpy_server.worker.exception import WorkerNotRunningError, WorkerStartError
from questionpy_server.worker.runtime.messages import MessageToWorker, MessageToServer, MessageIds, WorkerError, \
    InitWorker, LoadQPyPackage, Exit, GetQPyPackageManifest, GetOptionsForm, CreateQuestionFromOptions
from questionpy_server.worker.worker import WorkerState, Worker

log = logging.getLogger(__name__)
_T = TypeVar("_T", bound=MessageToServer)


class BaseWorker(Worker, ABC):
    """Base class implementing some common functionality of workers."""

    def __init__(self, package: Path, limits: Optional[WorkerResourceLimits]):
        super().__init__(package, limits)

        self._observe_task: Optional[asyncio.Task] = None

        self._connection: Optional[ServerToWorkerConnection] = None
        self._expected_incoming_messages: list[tuple[MessageIds, asyncio.Future]] = []

    async def _initialize(self) -> None:
        """Initializes an already running worker and starts the observe task.

        Should be called by subclasses in :meth:`start` after they have started the worker itself."""
        self.state = WorkerState.IDLE
        self._observe_task = asyncio.create_task(self._observe(), name='observe worker task')

        try:
            await self._send_and_wait_response(InitWorker(limits=self.limits), InitWorker.Response)
            await self._send_and_wait_response(LoadQPyPackage(path=str(self.package), main=True),
                                               LoadQPyPackage.Response)
        except WorkerNotRunningError as e:
            raise WorkerStartError("Worker has exited before or during initialization.") from e

    def send(self, message: MessageToWorker) -> None:
        if self._connection is None or self._observe_task is None or self._observe_task.done():
            raise WorkerNotRunningError()
        self._connection.send_message(message)

    async def _send_and_wait_response(self, message: MessageToWorker, expected_response_message: Type[_T]) -> _T:
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
                    for future in [fut for expected_id, fut in self._expected_incoming_messages if
                                   expected_id == cause_id]:
                        future.set_exception(exception)
                        self._expected_incoming_messages.remove((cause_id, future))
                else:
                    cur_id = message.message_id
                    for future in [fut for expected_id, fut in self._expected_incoming_messages if
                                   expected_id == cur_id]:
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
            except asyncio.TimeoutError:
                log.info("Worker was killed because it did not stop gracefully")

    async def get_manifest(self) -> ComparableManifest:
        msg = GetQPyPackageManifest(path=str(self.package))
        ret = await self._send_and_wait_response(msg, GetQPyPackageManifest.Response)
        return ComparableManifest(**ret.manifest.dict())

    async def get_options_form(self, question_state: Optional[bytes]) \
            -> tuple[OptionsFormDefinition, dict[str, object]]:
        question_state_str = None if question_state is None else question_state.decode()
        msg = GetOptionsForm(question_state=question_state_str)
        ret = await self._send_and_wait_response(msg, GetOptionsForm.Response)
        return ret.definition, ret.form_data

    async def create_question_from_options(self, old_state: Optional[bytes], form_data: dict[str, object]) \
            -> Question:
        question_state_str = None if old_state is None else old_state.decode()
        msg = CreateQuestionFromOptions(question_state=question_state_str, form_data=form_data)
        ret = await self._send_and_wait_response(msg, CreateQuestionFromOptions.Response)

        new_state_str = json.dumps(ret.state)

        return Question(
            question_state=new_state_str,
            scoring_method=ScoringMethod.ALWAYS_MANUAL_SCORING_REQUIRED,
            response_analysis_by_variant=False
        )
