from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Extra, FilePath, HttpUrl, Json, conint, constr


class PackageType(Enum):
    library = 'library'
    questiontype = 'questiontype'
    question = 'question'


class PackageInfo(BaseModel):
    class Config:
        extra = Extra.forbid
        use_enum_values = True

    package_hash: str
    short_name: str
    name: Dict[str, str]
    version: constr(regex=r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
                          r'(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
                          r'(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$')
    type: PackageType
    languages: List[str]
    author: Optional[str]
    url: Optional[HttpUrl]
    description: Optional[Dict[str, str]]
    icon: Optional[Union[FilePath, HttpUrl]]
    license: Optional[str]
    tags: Optional[List[str]]


class OptionsFormDefinition(BaseModel):
    pass

    class Config:
        extra = Extra.forbid


class QuestionStateHash(BaseModel):
    question_state_hash: str
    context: Optional[int]


class QuestionCreateArguments(BaseModel):
    class Config:
        extra = Extra.forbid

    form_data: Optional[Dict[str, Any]]


class GradingMethod(Enum):
    ALWAYS_MANUAL_GRADING_REQUIRED = 'ALWAYS_MANUAL_GRADING_REQUIRED'
    AUTOMATICALLY_GRADABLE = 'AUTOMATICALLY_GRADABLE'
    AUTOMATICALLY_GRADABLE_WITH_COUNTBACK = 'AUTOMATICALLY_GRADABLE_WITH_COUNTBACK'


class ResponseClass(BaseModel):
    class Config:
        extra = Extra.forbid

    response_class: str
    fraction: float


class Subquestion(BaseModel):
    class Config:
        extra = Extra.forbid

    subquestion_id: str
    max_fraction: Optional[float]
    response_classes: Optional[List[ResponseClass]]


class Question(BaseModel):
    class Config:
        extra = Extra.forbid
        use_enum_values = True

    question_state: Optional[Json]
    question_state_hash: Optional[str]
    num_variants: conint(ge=1, strict=True) = 1
    num_subquestions: conint(ge=1, strict=True) = 1
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
    variant: conint(ge=1, strict=True)


class UiField(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str
    type: str
    default: Optional[str]
    validation_regex: Optional[str]
    required: bool
    correct_response: Optional[str]


class UiCallJavascriptItem(BaseModel):
    class Config:
        extra = Extra.forbid

    module: str
    function: str
    args: str


class UiFile(BaseModel):
    class Config:
        extra = Extra.forbid

    name: str
    data: str
    mime_type: Optional[str]


class Ui(BaseModel):
    class Config:
        extra = Extra.forbid

    fields: List[UiField]
    text: str
    include_inline_css: Optional[str]
    include_css_file: Optional[str]
    include_javascript_modules: Optional[List[str]]
    call_javascript: Optional[List[UiCallJavascriptItem]]
    files: Optional[List[UiFile]]


class Attempt(BaseModel):
    class Config:
        extra = Extra.forbid

    variant: Optional[conint(ge=1, strict=True)]
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
    AUTOMATICALLY_GRADED = 'AUTOMATICALLY_GRADED'
    NEEDS_MANUAL_GRADING = 'NEEDS_MANUAL_GRADING'
    RESPONSE_NOT_GRADABLE = 'RESPONSE_NOT_GRADABLE'
    INVALID_RESPONSE = 'INVALID_RESPONSE'


class ClassificationItem(BaseModel):
    class Config:
        extra = Extra.forbid

    subquestion_id: str
    response_class: str
    response: str
    fraction: float


class GradedField(BaseModel):
    class Config:
        extra = Extra.forbid

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
    class Config:
        extra = Extra.forbid

    package_not_found: bool
    question_state_not_found: bool


class Code(Enum):
    NOT_IMPLEMENTED = 'NOT_IMPLEMENTED'
    DOWNGRADE_NOT_POSSIBLE = 'DOWNGRADE_NOT_POSSIBLE'
    PACKAGE_MISMATCH = 'PACKAGE_MISMATCH'
    CURRENT_QUESTION_STATE_INVALID = 'CURRENT_QUESTION_STATE_INVALID'
    MAJOR_VERSION_MISMATCH = 'MAJOR_VERSION_MISMATCH'
    OTHER_ERROR = 'OTHER_ERROR'


class QuestionStateMigrationError(BaseModel):
    class Config:
        extra = Extra.forbid
        use_enum_values = True

    code: Code
    reason: Optional[str]
