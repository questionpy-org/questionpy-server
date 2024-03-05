#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ByteSize, ConfigDict, Field, FilePath, HttpUrl

from questionpy_common.api.attempt import AttemptModel
from questionpy_common.api.question import QuestionModel
from questionpy_common.elements import OptionsFormDefinition


class PackageType(Enum):
    LIBRARY = "LIBRARY"
    QUESTIONTYPE = "QUESTIONTYPE"
    QUESTION = "QUESTION"


class PackageInfo(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    package_hash: str
    short_name: str
    namespace: str
    name: dict[str, str]
    version: Annotated[
        str,
        Field(
            pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
            r"(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$"
        ),
    ]
    type: PackageType
    author: str | None
    url: HttpUrl | None
    languages: list[str] | None
    description: dict[str, str] | None
    icon: FilePath | HttpUrl | None
    license: str | None
    tags: list[str] | None


class MainBaseModel(BaseModel):
    pass


class RequestBaseData(MainBaseModel):
    context: int | None = None


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
    scoring_state: str | None = None
    response: dict[str, Any] | None = None


class AttemptScoreArguments(AttemptViewArguments):
    response: dict[str, Any]
    responses: list[dict[str, object]] | None = None
    generate_hint: bool


class NotFoundStatusWhat(Enum):
    PACKAGE = "PACKAGE"
    QUESTION_STATE = "QUESTION_STATE"


class NotFoundStatus(BaseModel):
    what: NotFoundStatusWhat


class QuestionStateMigrationErrorCode(Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    DOWNGRADE_NOT_POSSIBLE = "DOWNGRADE_NOT_POSSIBLE"
    PACKAGE_MISMATCH = "PACKAGE_MISMATCH"
    CURRENT_QUESTION_STATE_INVALID = "CURRENT_QUESTION_STATE_INVALID"
    MAJOR_VERSION_MISMATCH = "MAJOR_VERSION_MISMATCH"
    OTHER_ERROR = "OTHER_ERROR"


class QuestionStateMigrationError(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    code: QuestionStateMigrationErrorCode
    reason: str | None = None


class Usage(BaseModel):
    requests_in_process: int
    requests_in_queue: int


class ServerStatus(BaseModel):
    name: str = "questionpy-server"
    version: Annotated[
        str,
        Field(
            pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
            r"(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$"
        ),
    ]
    allow_lms_packages: bool
    max_package_size: ByteSize
    usage: Usage | None
