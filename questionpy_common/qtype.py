from abc import ABC
from .elements import OptionsFormDefinition
from .manifest import Manifest


class BaseQuestion(ABC):
    question_state: str


class BaseQuestionType(ABC):
    def __init__(self, manifest: Manifest):
        self.manifest = manifest

    def get_options_form_definition(self) -> OptionsFormDefinition:
        raise NotImplementedError()

    def create_question_from_options(self, form_data: dict) -> BaseQuestion:
        """Create a new question from options form data. May raise OptionsFormValidationError on a validation error."""
        raise NotImplementedError()

    def create_question_from_state(self, question_state: str) -> BaseQuestion:
        raise NotImplementedError()


class OptionsFormValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        """There was at least one validation error."""
        self.errors = errors  # input element name -> error description
        super().__init__("Form input data could not be validated successfully.")

