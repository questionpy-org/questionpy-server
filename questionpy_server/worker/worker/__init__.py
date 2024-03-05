#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from abc import ABC, abstractmethod
from enum import Enum

from questionpy_common.api.attempt import AttemptModel, AttemptScoredModel
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.environment import RequestUser, WorkerResourceLimits
from questionpy_server.api.models import AttemptStarted, QuestionCreated
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.worker import WorkerResources
from questionpy_server.worker.runtime.messages import MessageToWorker
from questionpy_server.worker.runtime.package_location import PackageLocation


class WorkerState(Enum):
    NOT_RUNNING = 1
    IDLE = 2
    SERVER_AWAITS_RESPONSE = 3  # server send a message to worker and is waiting for a response
    WORKER_AWAITS_RESPONSE = 4  # worker send a request/message to server and server is now processing the request


class Worker(ABC):
    """Interface for worker implementations."""

    def __init__(self, package: PackageLocation, limits: WorkerResourceLimits | None) -> None:
        self.package = package
        self.limits = limits
        self.state = WorkerState.NOT_RUNNING

    @abstractmethod
    async def start(self) -> None:
        """Start and initialize the worker process.

        Only after this method finishes is the worker ready to accept other messages.
        """

    @abstractmethod
    async def stop(self, timeout: float) -> None:
        """Ask the worker to exit gracefully and wait for at most timeout seconds before killing it.

        If the worker is not running for any reason, this method should do nothing.
        """

    @abstractmethod
    async def kill(self) -> None:
        """Kill the worker process without waiting for it to exit.

        If the worker is not running for any reason, this method should do nothing.
        """

    @abstractmethod
    def send(self, message: MessageToWorker) -> None:
        """Send a message to the worker."""

    @abstractmethod
    async def get_resource_usage(self) -> WorkerResources | None:
        """Get the worker's current resource usage. If unknown or unsupported, return None."""

    @abstractmethod
    async def get_manifest(self) -> ComparableManifest:
        """Get manifest of the main package in the worker."""

    @abstractmethod
    async def get_options_form(
        self, request_user: RequestUser, question_state: str | None
    ) -> tuple[OptionsFormDefinition, dict[str, object]]:
        """Get the form used to create a new or edit an existing question.

        Args:
            request_user: Information on the user this request is for.
            question_state: The current question state if editing, or ``None`` if creating a new question.

        Returns:
             Tuple of the form definition and the current data of the inputs.
        """

    @abstractmethod
    async def create_question_from_options(
        self, request_user: RequestUser, old_state: str | None, form_data: dict[str, object]
    ) -> QuestionCreated:
        """Create or update the question (state) with the form data from a submitted question edit form.

        Args:
            request_user: Information on the user this request is for.
            old_state: The current question state if editing, or ``None`` if creating a new question.
            form_data: Form data from a submitted question edit form.

        Returns:
            New question.
        """

    @abstractmethod
    async def start_attempt(self, request_user: RequestUser, question_state: str, variant: int) -> AttemptStarted:
        """Start an attempt at this question with the given variant.

        Args:
            request_user: Information on the user this request is for.
            question_state: The question that is to be attempted.
            variant: Not implemented.

        Returns:
            The started attempt consisting of opaque attempt state and metadata.
        """

    @abstractmethod
    async def get_attempt(
        self,
        *,
        request_user: RequestUser,
        question_state: str,
        attempt_state: str,
        scoring_state: str | None = None,
        response: dict | None = None,
    ) -> AttemptModel:
        """Create an attempt object for a previously started attempt.

        Args:
            request_user: Information on the user this request is for.
            question_state: The question the attempt belongs to.
            attempt_state: The `attempt_state` attribute of an attempt which was previously returned by
                           :meth:`start_attempt`.
            scoring_state: Not implemented.
            response: The response currently entered by the student.

        Returns:
            Metadata of the attempt.
        """

    @abstractmethod
    async def score_attempt(
        self,
        *,
        request_user: RequestUser,
        question_state: str,
        attempt_state: str,
        scoring_state: str | None = None,
        response: dict,
    ) -> AttemptScoredModel:
        """TODO: write docstring."""
