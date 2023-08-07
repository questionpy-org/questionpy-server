#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from abc import ABC, abstractmethod
from typing import Optional

from .elements import OptionsFormDefinition
from .models import QuestionModel, AttemptModel


class BaseAttempt(ABC):
    @abstractmethod
    def export_attempt_state(self) -> str:
        """Serialize this attempt's relevant data.

        A future call to :meth:`BaseQuestion.view_attempt` should result in an attempt object identical to the one which
        exported the state.
        """

    @abstractmethod
    def export(self) -> AttemptModel:
        """Get metadata about this attempt."""


class BaseQuestion(ABC):
    @abstractmethod
    def start_attempt(self, variant: int) -> BaseAttempt:
        """Start an attempt at this question with the given variant.

        Args:
            variant: Not implemented.

        Returns:
            A :class:`BaseAttempt` object representing the attempt.
        """

    @abstractmethod
    def view_attempt(self, attempt_state: str, scoring_state: Optional[str] = None,
                     response: Optional[dict] = None) -> BaseAttempt:
        """Create an attempt object for a previously started attempt.

        Args:
            attempt_state: The `attempt_state` attribute of an attempt which was previously returned by
                           :meth:`start_attempt`.
            scoring_state: Not implemented.
            response: The response currently entered by the student.

        Returns:
            A :class:`BaseAttempt` object which should be identical to the one which generated the given state(s).
        """

    @abstractmethod
    def export_question_state(self) -> str:
        """Serialize this question's relevant data.

        A future call to :meth:`BaseQuestionType.create_question_from_state` should result in a question object
        identical to the one which exported the state.
        """

    @abstractmethod
    def export(self) -> QuestionModel:
        """Get metadata about this question."""


class BaseQuestionType(ABC):
    @abstractmethod
    def get_options_form(self, question_state: Optional[str]) -> tuple[OptionsFormDefinition, dict[str, object]]:
        """Get the form used to create a new or edit an existing question.

        Args:
            question_state: The current question state if editing, or ``None`` if creating a new question.

        Returns:
            Tuple of the form definition and the current data of the inputs.
        """

    @abstractmethod
    def create_question_from_options(self, old_state: Optional[str], form_data: dict[str, object]) -> BaseQuestion:
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
    def create_question_from_state(self, question_state: str) -> BaseQuestion:
        """Deserialize the given question state, returning a question object equivalent to the one which exported it."""


class OptionsFormValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        """There was at least one validation error."""
        self.errors = errors  # input element name -> error description
        super().__init__("Form input data could not be validated successfully.")
