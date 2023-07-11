#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from abc import ABC, abstractmethod
from typing import Optional

from .elements import OptionsFormDefinition
from .manifest import Manifest


class BaseQuestion(ABC):
    question_state: dict[str, object]


class BaseQuestionType(ABC):
    def __init__(self, manifest: Manifest):
        self.manifest = manifest

    @abstractmethod
    def get_options_form(self, question_state: Optional[dict[str, object]]) \
            -> tuple[OptionsFormDefinition, dict[str, object]]:
        """Get the form used to create a new or edit an existing question.

        Args:
            question_state: The current question state if editing, or ``None`` if creating a new question.

        Returns:
            Tuple of the form definition and the current data of the inputs.
        """

    @abstractmethod
    def create_question_from_options(self, old_state: Optional[dict[str, object]],
                                     form_data: dict[str, object]) -> BaseQuestion:
        """Create or update the question (state) with the form data from a submitted question edit form.

        Args:
            old_state: Current question state if editing, or ``None`` if creating a new question.
            form_data: Form data from a submitted question edit form.

        Returns:
            New question.

        Raises:
            OptionsFormValidationError: When `form_data` is invalid.
        """

    @abstractmethod
    def create_question_from_state(self, question_state: dict[str, object]) -> BaseQuestion:
        pass


class OptionsFormValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        """There was at least one validation error."""
        self.errors = errors  # input element name -> error description
        super().__init__("Form input data could not be validated successfully.")
