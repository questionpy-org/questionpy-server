#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ByteSize, ConfigDict, Field

from questionpy_common.api.question import QuestionModel
from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.manifest import PackageType


class PackageInfo(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    short_name: str
    namespace: str
    name: dict[str, str]
    type: PackageType
    author: str | None
    url: str | None
    languages: set[str] | None
    description: dict[str, str] | None
    icon: str | None
    license: str | None
    tags: set[str] | None


class PackageVersionSpecificInfo(BaseModel):
    package_hash: str
    version: Annotated[
        str,
        Field(
            pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
            r"(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
            r"(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$"
        ),
    ]


class PackageVersionInfo(PackageInfo, PackageVersionSpecificInfo):
    pass


class PackageVersionsInfo(BaseModel):
    manifest: PackageInfo
    versions: list[PackageVersionSpecificInfo]


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


class AttemptViewArguments(RequestBaseData):
    attempt_state: str
    scoring_state: str | None = None
    response: dict[str, Any] | None = None


class AttemptScoreArguments(AttemptViewArguments):
    response: dict[str, Any]
    responses: list[dict[str, object]] | None = None
    generate_hint: bool


class RequestErrorCode(Enum):
    QUEUE_WAITING_TIMEOUT = "QUEUE_WAITING_TIMEOUT"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    INVALID_PACKAGE = "INVALID_PACKAGE"
    INVALID_REQUEST = "INVALID_REQUEST"
    PACKAGE_ERROR = "PACKAGE_ERROR"
    CALLBACK_API_ERROR = "CALLBACK_API_ERROR"
    SERVER_ERROR = "SERVER_ERROR"


class RequestError(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    error_code: RequestErrorCode
    temporary: bool
    reason: str | None = None


class QuestionStateMigrationErrorCode(Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    DOWNGRADE_NOT_POSSIBLE = "DOWNGRADE_NOT_POSSIBLE"
    PACKAGE_MISMATCH = "PACKAGE_MISMATCH"
    CURRENT_QUESTION_STATE_INVALID = "CURRENT_QUESTION_STATE_INVALID"
    MAJOR_VERSION_MISMATCH = "MAJOR_VERSION_MISMATCH"
    OTHER_ERROR = "OTHER_ERROR"


class QuestionStateMigrationError(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    error_code: QuestionStateMigrationErrorCode
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
