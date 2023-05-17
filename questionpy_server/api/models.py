from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, FilePath, HttpUrl, Json

from questionpy_common.elements import OptionsFormDefinition


class PackageType(Enum):
    LIBRARY = 'LIBRARY'
    QUESTIONTYPE = 'QUESTIONTYPE'
    QUESTION = 'QUESTION'


class PackageInfo(BaseModel):
    class Config:
        use_enum_values = True

    package_hash: str
    short_name: str
    namespace: str
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


class OptionalQuestionStateHash(BaseModel):
    question_state_hash: Optional[str]
    context: Optional[int] = None


class QuestionStateHash(OptionalQuestionStateHash):
    question_state_hash: str


class QuestionEditFormResponse(BaseModel):
    definition: OptionsFormDefinition
    form_data: dict[str, object]


class QuestionCreateArguments(OptionalQuestionStateHash):
    form_data: dict[str, object]


class ScoringMethod(Enum):
    ALWAYS_MANUAL_SCORING_REQUIRED = 'ALWAYS_MANUAL_SCORING_REQUIRED'
    AUTOMATICALLY_SCORABLE = 'AUTOMATICALLY_SCORABLE'
    AUTOMATICALLY_SCORABLE_WITH_COUNTBACK = 'AUTOMATICALLY_SCORABLE_WITH_COUNTBACK'


class ResponseClass(BaseModel):
    response_class: Annotated[str, Field(max_length=30, strict=True)]
    score: float


class Subquestion(BaseModel):
    subquestion_id: Annotated[str, Field(max_length=30, strict=True)]
    score_max: Optional[float]
    response_classes: Optional[List[ResponseClass]]


class Question(BaseModel):
    class Config:
        use_enum_values = True

    question_state: str
    question_state_hash: str
    num_variants: Annotated[int, Field(ge=1, strict=True)] = 1
    num_subquestions: Annotated[int, Field(ge=1, strict=True)] = 1
    score_min: float = 0
    score_max: float = 1
    scoring_method: ScoringMethod
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
    include_inline_css: Optional[str] = None
    include_css_file: Optional[str] = None
    include_javascript_modules: List[str] = []
    call_javascript: List[UiCallJavascriptItem] = []
    files: List[UiFile] = []


class Attempt(BaseModel):
    variant: Annotated[int, Field(ge=1, strict=True)]
    question_summary: Optional[str] = None
    right_answer_summary: Optional[str] = None
    ui: Ui


class AttemptStarted(Attempt):
    attempt_state: str


class AttemptViewArguments(QuestionStateHash):
    attempt_state: Json
    scoring_state: Optional[Json]
    response: Optional[Dict[str, Any]]


class Response(BaseModel):
    response: Optional[Dict[str, Any]]


class AttemptScoreArguments(AttemptViewArguments):
    responses: Optional[List[Response]] = None
    generate_hint: bool


class ScoringCode(Enum):
    AUTOMATICALLY_SCORED = 'AUTOMATICALLY_SCORED'
    NEEDS_MANUAL_SCORING = 'NEEDS_MANUAL_SCORING'
    RESPONSE_NOT_SCORABLE = 'RESPONSE_NOT_SCORABLE'
    INVALID_RESPONSE = 'INVALID_RESPONSE'


class ClassificationItem(BaseModel):
    subquestion_id: Annotated[str, Field(max_length=30, strict=True)]
    response_class: Annotated[str, Field(max_length=30, strict=True)]
    response: str
    score: float


class ScoredField(BaseModel):
    name: str
    correct: Optional[bool]
    score: Optional[float]
    max_score: Optional[float]
    feedback: Optional[str]


class AttemptScored(Attempt):
    scoring_state: Optional[Json]
    scoring_code: ScoringCode
    score: Optional[float]
    specific_feedback: Optional[str] = None
    hint: Optional[str] = None
    more_hints_available: Optional[bool] = None
    response_summary: Optional[str] = None
    classification: Optional[List[ClassificationItem]] = None
    scored_fields: Optional[List[ScoredField]]


class PackageQuestionStateNotFound(BaseModel):
    package_not_found: bool
    question_state_not_found: bool


class QuestionStateMigrationErrorCode(Enum):
    NOT_IMPLEMENTED = 'NOT_IMPLEMENTED'
    DOWNGRADE_NOT_POSSIBLE = 'DOWNGRADE_NOT_POSSIBLE'
    PACKAGE_MISMATCH = 'PACKAGE_MISMATCH'
    CURRENT_QUESTION_STATE_INVALID = 'CURRENT_QUESTION_STATE_INVALID'
    MAJOR_VERSION_MISMATCH = 'MAJOR_VERSION_MISMATCH'
    OTHER_ERROR = 'OTHER_ERROR'


class QuestionStateMigrationError(BaseModel):
    class Config:
        use_enum_values = True

    code: QuestionStateMigrationErrorCode
    reason: Optional[str] = None
