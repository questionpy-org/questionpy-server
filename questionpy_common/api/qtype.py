#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from questionpy_common.api.package import BasePackageInterface
from questionpy_common.error import QPyBaseError

if TYPE_CHECKING:
    from pydantic import JsonValue

    from questionpy_common.elements import OptionsFormDefinition

    from .question import QuestionInterface

__all__ = [
    "InvalidAttemptStateError",
    "InvalidQuestionStateError",
    "MigrationError",
    "MigrationErrorKind",
    "OptionsFormValidationError",
    "QuestionTypeInterface",
]


class QuestionTypeInterface(BasePackageInterface, Protocol):
    """Describes the API of a question type between the worker runtime and the package."""

    @abstractmethod
    def get_options_form(self, question_state: str | None) -> tuple[OptionsFormDefinition, dict[str, JsonValue]]:
        """Get the form used to create a new or edit an existing question.

        Args:
            question_state: The current question state if editing, or ``None`` if creating a new question.

        Returns:
            Tuple of the form definition and the current data of the inputs.
        """

    @abstractmethod
    def create_question_from_options(self, old_state: str | None, form_data: dict[str, JsonValue]) -> QuestionInterface:
        """Create or update the question (state) with the form data from a submitted question edit form.

        Args:
            old_state: Current question state if editing, or ``None`` if creating a new question.
            form_data: Form data from a submitted question edit form.

        Returns:
            New or updated question object.

        Raises:
            OptionsFormValidationError: When `form_data` is invalid.
        """

    @abstractmethod
    def create_question_from_state(self, question_state: str) -> QuestionInterface:
        """Deserialize the given question state, returning a question object equivalent to the one which exported it.

        Raises:
            InvalidQuestionStateError: When the given question state is invalid and cannot be reused.
        """

    @abstractmethod
    def upgrade(self, question_state: str) -> str:
        """Upgrade the given question state to the question state version of the main package."""

    @abstractmethod
    def downgrade(self, question_state: str, to: int) -> str:
        """Downgrade the given question state to the provided question state version of the main package."""

    @abstractmethod
    def sidegrade(self, question_state: str) -> str:
        """Sidegrade the given question state to the version used by the main package."""


class OptionsFormValidationError(QPyBaseError):
    def __init__(self, errors: dict[str, str], reason: str | None = None, temporary: bool = False):  # noqa: FBT001, FBT002
        """There was at least one validation error."""
        self.errors = errors  # input element name -> error description
        super().__init__("Form input data could not be validated successfully.", reason=reason, temporary=temporary)


class InvalidAttemptStateError(QPyBaseError):
    """Error to raise when your package cannot parse the attempt state it is given."""


class InvalidQuestionStateError(QPyBaseError):
    """Error to raise when your package cannot parse the question state it is given."""


class MigrationErrorKind(Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    NOT_POSSIBLE = "NOT_POSSIBLE"
    PACKAGE_MISSMATCH = "PACKAGE_MISSMATCH"
    QUESTION_STATE_INVALID = "QUESTION_STATE_INVALID"
    FAILED = "FAILED"
    DISCOVERY_ERROR = "DISCOVERY_ERROR"
    OTHER_ERROR = "OTHER_ERROR"


class MigrationError(QPyBaseError):
    """The migration failed."""

    def __init__(
        self, *args: object, kind: MigrationErrorKind, reason: str | None = None, temporary: bool = False
    ) -> None:
        self.kind = kind
        super().__init__(*args, reason=reason, temporary=temporary)
