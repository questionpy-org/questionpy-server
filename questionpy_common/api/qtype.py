#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

from questionpy_common.api.package import BasePackageInterface

if TYPE_CHECKING:
    from questionpy_common.elements import OptionsFormDefinition

    from . import PlainMapping
    from .question import QuestionInterface

__all__ = ["InvalidQuestionStateError", "OptionsFormValidationError", "QuestionTypeInterface"]


class QuestionTypeInterface(BasePackageInterface, Protocol):
    @abstractmethod
    def get_options_form(self, question_state: str | None) -> tuple[OptionsFormDefinition, PlainMapping]:
        """Get the form used to create a new or edit an existing question.

        Args:
            question_state: The current question state if editing, or ``None`` if creating a new question.

        Returns:
            Tuple of the form definition and the current data of the inputs.
        """

    @abstractmethod
    def create_question_from_options(self, old_state: str | None, form_data: PlainMapping) -> QuestionInterface:
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


class OptionsFormValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        """There was at least one validation error."""
        self.errors = errors  # input element name -> error description
        super().__init__("Form input data could not be validated successfully.")


class InvalidQuestionStateError(Exception):
    """Error to raise when your package cannot parse the question state it is given."""
