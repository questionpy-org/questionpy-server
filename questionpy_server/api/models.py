from __future__ import annotations
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, FilePath, HttpUrl, Json


class PackageType(Enum):
    library = 'LIBRARY'
    questiontype = 'QUESTIONTYPE'
    question = 'QUESTION'


class PackageInfo(BaseModel):
    class Config:
        use_enum_values = True

    package_hash: str
    short_name: str
    name: Dict[str, str]
    version: Annotated[str, Field(regex=r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
                                        r'(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
                                        r'(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
                                        r'(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$')]
    type: PackageType
    author: Optional[str]
    url: Optional[HttpUrl]
    languages: Optional[List[str]]
    description: Optional[Dict[str, str]]
    icon: Optional[Union[FilePath, HttpUrl]]
    license: Optional[str]
    tags: Optional[List[str]]


class QuestionStateHash(BaseModel):
    question_state_hash: str
    context: Optional[int]


class QuestionCreateArguments(BaseModel):
    form_data: Optional[Dict[str, Any]]


class GradingMethod(Enum):
    always_manual_grading_required = 'ALWAYS_MANUAL_GRADING_REQUIRED'
    automatically_gradable = 'AUTOMATICALLY_GRADABLE'
    automatically_gradable_with_countback = 'AUTOMATICALLY_GRADABLE_WITH_COUNTBACK'


class ResponseClass(BaseModel):
    response_class: str
    fraction: float


class Subquestion(BaseModel):
    subquestion_id: str
    max_fraction: Optional[float]
    response_classes: Optional[List[ResponseClass]]


class Question(BaseModel):
    class Config:
        use_enum_values = True

    question_state: Optional[Json]
    question_state_hash: Optional[str]
    num_variants: Annotated[int, Field(ge=1, strict=True)] = 1
    num_subquestions: Annotated[int, Field(ge=1, strict=True)] = 1
    grade_min_fraction: float = 0
    grade_max_fraction: float = 1
    grading_method: GradingMethod
    penalty: Optional[float]
    random_guess_score: Optional[float]
    subquestions: Optional[List[Subquestion]]
    response_analysis_by_variant: bool
    render_every_view: bool = False
    general_feedback: Optional[str]


class AttemptStartArguments(QuestionStateHash):
    variant: Annotated[int, Field(ge=1, strict=True)]


class UiField(BaseModel):
    name: str
    type: str
    default: Optional[str]
    validation_regex: Optional[str]
    required: bool
    correct_response: Optional[str]


class UiCallJavascriptItem(BaseModel):
    module: str
    function: str
    args: str


class UiFile(BaseModel):
    name: str
    data: str
    mime_type: Optional[str]


class Ui(BaseModel):
    fields: List[UiField]
    text: str
    include_inline_css: Optional[str]
    include_css_file: Optional[str]
    include_javascript_modules: Optional[List[str]]
    call_javascript: Optional[List[UiCallJavascriptItem]]
    files: Optional[List[UiFile]]


class Attempt(BaseModel):
    variant: Annotated[Optional[int], Field(ge=1, strict=True)]
    question_summary: Optional[str]
    right_answer_summary: Optional[str]
    ui: Ui


class AttemptStarted(Attempt):
    attempt_state: str


class AttemptViewArguments(QuestionStateHash):
    attempt_state: Json
    grading_state: Optional[Json]
    response: Optional[Dict[str, Any]]


class Response(BaseModel):
    response: Optional[Dict[str, Any]]


class AttemptGradeArguments(AttemptViewArguments):
    responses: Optional[List[Response]]
    generate_hint: Optional[bool]


class GradingCode(Enum):
    automatically_graded = 'AUTOMATICALLY_GRADED'
    needs_manual_grading = 'NEEDS_MANUAL_GRADING'
    response_not_gradable = 'RESPONSE_NOT_GRADABLE'
    invalid_response = 'INVALID_RESPONSE'


class ClassificationItem(BaseModel):
    subquestion_id: str
    response_class: str
    response: str
    fraction: float


class GradedField(BaseModel):
    name: str
    correct: Optional[bool]
    fraction: Optional[float]
    max_fraction: Optional[float]
    feedback: Optional[str]


class AttemptGraded(Attempt):
    grading_state: Optional[Json]
    grading_code: GradingCode
    fraction: Optional[float]
    specific_feedback: Optional[str]
    hint: Optional[str]
    more_hints_available: Optional[bool]
    response_summary: Optional[str]
    classification: Optional[List[ClassificationItem]]
    graded_fields: Optional[List[GradedField]]


class PackageQuestionStateNotFound(BaseModel):
    package_not_found: bool
    question_state_not_found: bool


class Code(Enum):
    not_implemented = 'NOT_IMPLEMENTED'
    downgrade_not_possible = 'DOWNGRADE_NOT_POSSIBLE'
    package_mismatch = 'PACKAGE_MISMATCH'
    current_question_state_invalid = 'CURRENT_QUESTION_STATE_INVALID'
    major_version_mismatch = 'MAJOR_VERSION_MISMATCH'
    other_error = 'OTHER_ERROR'


class QuestionStateMigrationError(BaseModel):
    class Config:
        use_enum_values = True

    code: Code
    reason: Optional[str]
