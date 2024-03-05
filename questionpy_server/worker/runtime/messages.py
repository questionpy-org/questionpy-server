#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import traceback
from enum import IntEnum, unique
from struct import Struct
from typing import Any, ClassVar

from pydantic import BaseModel

from questionpy_common.api.attempt import AttemptModel, AttemptScoredModel
from questionpy_common.api.qtype import OptionsFormDefinition
from questionpy_common.api.question import QuestionModel
from questionpy_common.environment import RequestUser, WorkerResourceLimits
from questionpy_common.manifest import Manifest
from questionpy_server.worker.runtime.package_location import PackageLocation

messages_header_struct: Struct = Struct("=LL")
"""4 bytes unsigned long int message id and 4 bytes unsigned long int payload length"""


@unique
class MessageIds(IntEnum):
    """Message ids between worker and application server."""

    # Server to worker.
    INIT_WORKER = 0
    ENABLE_SANDBOX = 1
    TEST_SANDBOX_CRASH = 2
    EXIT = 3
    LOAD_QPY_PACKAGE = 10
    GET_QPY_PACKAGE_MANIFEST = 20
    GET_OPTIONS_FORM_DEFINITION = 30
    CREATE_QUESTION = 40

    START_ATTEMPT = 50
    VIEW_ATTEMPT = 51
    SCORE_ATTEMPT = 52

    # Worker to server.
    WORKER_STARTED = 1000
    SANDBOX_ENABLED = 1001
    TEST_SANDBOX_CRASH_FAILED = 1002
    LOADED_QPY_PACKAGE = 1010
    RETURN_QPY_PACKAGE_MANIFEST = 1020
    RETURN_OPTIONS_FORM_DEFINITION = 1030
    RETURN_CREATE_QUESTION = 1040

    RETURN_START_ATTEMPT = 1050
    RETURN_VIEW_ATTEMPT = 1051
    RETURN_SCORE_ATTEMPT = 1052

    ERROR = 1100


class Message(BaseModel):
    """Message base class."""

    message_id: ClassVar[MessageIds]
    Response: ClassVar[type["Message"]]


class MessageToWorker(Message):
    """A message from server to worker."""

    types: ClassVar[dict[int, type["MessageToWorker"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        MessageToWorker.types[cls.message_id] = cls


class MessageToServer(Message):
    """A message from worker to server."""

    types: ClassVar[dict[int, type["MessageToServer"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        MessageToServer.types[cls.message_id] = cls


class InitWorker(MessageToWorker):
    """Give worker some basic information."""

    message_id: ClassVar[MessageIds] = MessageIds.INIT_WORKER
    limits: WorkerResourceLimits | None = None
    worker_type: str

    class Response(MessageToServer):
        """Success message in return to InitWorker."""

        message_id: ClassVar[MessageIds] = MessageIds.WORKER_STARTED


class Exit(MessageToWorker):
    """Command from server to gracefully exit the worker process."""

    message_id: ClassVar[MessageIds] = MessageIds.EXIT


class LoadQPyPackage(MessageToWorker):
    """Load/import a QuestionPy package."""

    message_id: ClassVar[MessageIds] = MessageIds.LOAD_QPY_PACKAGE
    location: PackageLocation
    main: bool
    """Set this package as the main package and execute its entry point."""

    class Response(MessageToServer):
        """Success message in return to LoadQPyPackage."""

        message_id: ClassVar[MessageIds] = MessageIds.LOADED_QPY_PACKAGE


class GetQPyPackageManifest(MessageToWorker):
    """Get the manifest data of the main package, which must previously have been loaded."""

    message_id: ClassVar[MessageIds] = MessageIds.GET_QPY_PACKAGE_MANIFEST
    path: str

    class Response(MessageToServer):
        """Execute a QuestionPy package."""

        message_id: ClassVar[MessageIds] = MessageIds.RETURN_QPY_PACKAGE_MANIFEST
        manifest: Manifest


class GetOptionsForm(MessageToWorker):
    """Execute a QuestionPy package."""

    message_id: ClassVar[MessageIds] = MessageIds.GET_OPTIONS_FORM_DEFINITION
    request_user: RequestUser
    question_state: str | None
    """Old question state or ``None`` if the question is new."""

    class Response(MessageToServer):
        """Execute a QuestionPy package."""

        message_id: ClassVar[MessageIds] = MessageIds.RETURN_OPTIONS_FORM_DEFINITION
        definition: OptionsFormDefinition
        form_data: dict[str, object]


class CreateQuestionFromOptions(MessageToWorker):
    message_id: ClassVar[MessageIds] = MessageIds.CREATE_QUESTION
    request_user: RequestUser
    question_state: str | None
    """Old question state or ``None`` if the question is new."""
    form_data: dict[str, object]

    class Response(MessageToServer):
        message_id: ClassVar[MessageIds] = MessageIds.RETURN_CREATE_QUESTION
        question_state: str
        """New question state."""
        question_model: QuestionModel


class StartAttempt(MessageToWorker):
    message_id: ClassVar[MessageIds] = MessageIds.START_ATTEMPT
    request_user: RequestUser
    question_state: str
    variant: int

    class Response(MessageToServer):
        message_id: ClassVar[MessageIds] = MessageIds.RETURN_START_ATTEMPT
        attempt_state: str
        attempt_model: AttemptModel


class ViewAttempt(MessageToWorker):
    message_id: ClassVar[MessageIds] = MessageIds.VIEW_ATTEMPT
    request_user: RequestUser
    question_state: str
    attempt_state: str
    scoring_state: str | None
    response: dict | None

    class Response(MessageToServer):
        message_id: ClassVar[MessageIds] = MessageIds.RETURN_VIEW_ATTEMPT
        attempt_model: AttemptModel


class ScoreAttempt(MessageToWorker):
    message_id: ClassVar[MessageIds] = MessageIds.SCORE_ATTEMPT
    request_user: RequestUser
    question_state: str
    attempt_state: str
    scoring_state: str | None
    response: dict

    class Response(MessageToServer):
        message_id: ClassVar[MessageIds] = MessageIds.RETURN_SCORE_ATTEMPT
        attempt_scored_model: AttemptScoredModel


class WorkerError(MessageToServer):
    """Error message."""

    class ErrorType(IntEnum):
        """Error types."""

        UNKNOWN = 0
        MEMORY_EXCEEDED = 1

    message_id: ClassVar[MessageIds] = MessageIds.ERROR
    expected_response_id: MessageIds
    type: ErrorType
    message: str | None

    original_stacktrace: str | None = None
    """The original worker-side stacktrace."""

    @classmethod
    def from_exception(cls, error: Exception, cause: MessageToWorker) -> "WorkerError":
        """Get a WorkerError message from an exception."""
        if isinstance(error, MemoryError):
            error_type = WorkerError.ErrorType.MEMORY_EXCEEDED
        else:
            error_type = WorkerError.ErrorType.UNKNOWN

        if __debug__:
            original_stacktrace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            original_stacktrace = None

        return cls(
            type=error_type,
            message=str(error),
            expected_response_id=cause.Response.message_id,
            original_stacktrace=original_stacktrace,
        )

    def to_exception(self) -> Exception:
        """Get an exception from a WorkerError message."""
        message = self.message
        if __debug__ and self.original_stacktrace:
            # add_note (PEP 678) will be great for this when we're on Python 3.11.
            note = f"The original worker-side stacktrace follows:\n{self.original_stacktrace}"
            message = message + "\n" + note if message else note

        if self.type == WorkerError.ErrorType.MEMORY_EXCEEDED:
            return WorkerMemoryLimitExceededError(message)
        return WorkerUnknownError(message)


def get_message_bytes(message: Message) -> tuple[bytes, bytes | None]:
    json_str = message.model_dump_json()
    json_bytes = None
    message_length = 0
    empty_json_length = 2
    if len(json_str) > empty_json_length:
        # Only transmit non-empty json objects.
        json_bytes = json_str.encode()
        message_length = len(json_bytes)

    header = messages_header_struct.pack(type(message).message_id, message_length)
    return header, json_bytes


class InvalidMessageIdError(Exception):
    def __init__(self, message_id: int, length: int):
        super().__init__(f"Received unknown message with id {message_id} and length {length}.")


class WorkerMemoryLimitExceededError(Exception):
    pass


class WorkerUnknownError(Exception):
    pass
