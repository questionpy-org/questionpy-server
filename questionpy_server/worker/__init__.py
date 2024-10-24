#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel

from questionpy_common.api.attempt import AttemptModel, AttemptScoredModel, AttemptStartedModel
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.environment import RequestUser, WorkerResourceLimits
from questionpy_common.manifest import PackageFile
from questionpy_server.models import QuestionCreated
from questionpy_server.utils.manifest import ComparableManifest
from questionpy_server.worker.runtime.messages import MessageToServer, MessageToWorker
from questionpy_server.worker.runtime.package_location import PackageLocation


class WorkerResources(BaseModel):
    """Current resource usage."""

    memory: int
    cpu_time_since_last_call: float
    total_cpu_time: float


class WorkerState(Enum):
    NOT_RUNNING = 1
    IDLE = 2
    SERVER_AWAITS_RESPONSE = 3  # server send a message to worker and is waiting for a response
    WORKER_AWAITS_RESPONSE = 4  # worker send a request/message to server and server is now processing the request


@dataclass
class PackageFileData:
    """Represents a file read from a package."""

    size: int
    """The total size of the file in bytes."""
    mime_type: str | None
    """Mime type as reported by the package.

    Usually this is derived from the file extension at build time and listed in the manifest.
    """
    data: bytes


_M = TypeVar("_M", bound=MessageToServer)


class Worker(ABC):
    """Interface for worker implementations."""

    def __init__(self, package: PackageLocation, limits: WorkerResourceLimits | None) -> None:
        super().__init__()
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
    async def send_and_wait_for_response(self, message: MessageToWorker, expected_response_message: type[_M]) -> _M:
        """Send a message and wait for a response of the given type."""

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
    async def start_attempt(self, request_user: RequestUser, question_state: str, variant: int) -> AttemptStartedModel:
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

    @abstractmethod
    async def get_static_file(self, path: str) -> PackageFileData:
        """Reads the static file at the given path in the package.

        Args:
            path: Path relative to the `dist` directory of the package.

        Raises:
            FileNotFoundError: If no static file exists at the given path.
        """

    @abstractmethod
    async def get_static_file_index(self) -> dict[str, PackageFile]:
        """Returns the index of static files as declared in the package's manifest."""
