#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union

from pydantic import ConfigDict, BaseModel, Field, FilePath, HttpUrl, Json, ByteSize
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.models import AttemptModel, QuestionModel


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


class QuestionViewArguments(RequestBaseData):
    question_state: str


class QuestionCreated(QuestionModel):
    question_state: str


class AttemptStartArguments(RequestBaseData):
    variant: Annotated[int, Field(ge=1, strict=True)]


class AttemptStarted(AttemptModel):
    attempt_state: str


class AttemptViewArguments(RequestBaseData):
    attempt_state: str
    scoring_state: Optional[str] = None
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


class AttemptScored(AttemptModel):
    scoring_state: Optional[Json] = None
    scoring_code: ScoringCode
    score: Optional[float] = None
    specific_feedback: Optional[str] = None
    hint: Optional[str] = None
    more_hints_available: Optional[bool] = None
    response_summary: Optional[str] = None
    classification: Optional[List[ClassificationItem]] = None
    scored_fields: Optional[List[ScoredField]] = None


class NotFoundStatusWhat(Enum):
    PACKAGE = 'PACKAGE'
    QUESTION_STATE = 'QUESTION_STATE'


class NotFoundStatus(BaseModel):
    what: NotFoundStatusWhat


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


class Usage(BaseModel):
    requests_in_process: int
    requests_in_queue: int


class ServerStatus(BaseModel):
    name: str = 'questionpy-server'
    version: Annotated[str, Field(pattern=r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
                                          r'(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
                                          r'(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
                                          r'(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$')]
    allow_lms_packages: bool
    max_package_size: ByteSize
    usage: Optional[Usage]
