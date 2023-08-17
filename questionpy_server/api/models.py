#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import ConfigDict, BaseModel, Field, FilePath, HttpUrl, Json

from questionpy_common.elements import OptionsFormDefinition


class PackageType(Enum):
    LIBRARY = 'LIBRARY'
    QUESTIONTYPE = 'QUESTIONTYPE'
    QUESTION = 'QUESTION'


class PackageInfo(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    package_hash: str
    short_name: str
    namespace: str
    name: Dict[str, str]
    version: Annotated[str, Field(pattern=r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
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


class MainBaseModel(BaseModel):
    pass


class RequestBaseData(MainBaseModel):
    context: Optional[int] = None


class QuestionEditFormResponse(BaseModel):
    definition: OptionsFormDefinition
    form_data: dict[str, object]


class QuestionCreateArguments(RequestBaseData):
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
    score_max: Optional[float] = None
    response_classes: Optional[List[ResponseClass]] = None


class Question(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    question_state: str
    num_variants: Annotated[int, Field(ge=1, strict=True)] = 1
    num_subquestions: Annotated[int, Field(ge=1, strict=True)] = 1
    score_min: float = 0
    score_max: float = 1
    scoring_method: ScoringMethod
    penalty: Optional[float] = None
    random_guess_score: Optional[float] = None
    subquestions: Optional[List[Subquestion]] = None
    response_analysis_by_variant: bool
    render_every_view: bool = False
    general_feedback: Optional[str] = None


class AttemptStartArguments(RequestBaseData):
    variant: Annotated[int, Field(ge=1, strict=True)]


class UiField(BaseModel):
    name: str
    type: str
    default: Optional[str] = None
    validation_regex: Optional[str] = None
    required: bool
    correct_response: Optional[str] = None


class UiCallJavascriptItem(BaseModel):
    module: str
    function: str
    args: str


class UiFile(BaseModel):
    name: str
    data: str
    mime_type: Optional[str] = None


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


class AttemptViewArguments(RequestBaseData):
    attempt_state: Json
    scoring_state: Optional[Json] = None
    response: Optional[Dict[str, Any]] = None


class Response(BaseModel):
    response: Optional[Dict[str, Any]] = None


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
    correct: Optional[bool] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    feedback: Optional[str] = None


class AttemptScored(Attempt):
    scoring_state: Optional[Json] = None
    scoring_code: ScoringCode
    score: Optional[float] = None
    specific_feedback: Optional[str] = None
    hint: Optional[str] = None
    more_hints_available: Optional[bool] = None
    response_summary: Optional[str] = None
    classification: Optional[List[ClassificationItem]] = None
    scored_fields: Optional[List[ScoredField]] = None


class PackageNotFound(BaseModel):
    package_not_found: bool


class QuestionStateMigrationErrorCode(Enum):
    NOT_IMPLEMENTED = 'NOT_IMPLEMENTED'
    DOWNGRADE_NOT_POSSIBLE = 'DOWNGRADE_NOT_POSSIBLE'
    PACKAGE_MISMATCH = 'PACKAGE_MISMATCH'
    CURRENT_QUESTION_STATE_INVALID = 'CURRENT_QUESTION_STATE_INVALID'
    MAJOR_VERSION_MISMATCH = 'MAJOR_VERSION_MISMATCH'
    OTHER_ERROR = 'OTHER_ERROR'


class QuestionStateMigrationError(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    code: QuestionStateMigrationErrorCode
    reason: Optional[str] = None
