#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from enum import Enum, StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from . import Localized

__all__ = [
    "AttemptFile",
    "AttemptModel",
    "AttemptScoredModel",
    "AttemptStartedModel",
    "AttemptUi",
    "CacheControl",
    "ClassifiedResponse",
    "DisplayRole",
    "FeedbackType",
    "JsModuleCall",
    "ScoreModel",
    "ScoredInputModel",
    "ScoredInputState",
    "ScoredSubquestionModel",
    "ScoringCode",
]


class CacheControl(Enum):
    SHARED_CACHE = "SHARED_CACHE"
    PRIVATE_CACHE = "PRIVATE_CACHE"
    NO_CACHE = "NO_CACHE"


class DisplayRole(StrEnum):
    DEVELOPER = "DEVELOPER"
    PROCTOR = "PROCTOR"
    SCORER = "SCORER"
    TEACHER = "TEACHER"


class FeedbackType(StrEnum):
    GENERAL_FEEDBACK = "GENERAL_FEEDBACK"
    SPECIFIC_FEEDBACK = "SPECIFIC_FEEDBACK"
    RIGHT_ANSWER = "RIGHT_ANSWER"
    HINT = "HINT"


class JsModuleCall(BaseModel):
    module: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_$/@.]+$")]
    """JS module name like @[package namespace]/[package short name]/[module].js"""
    function: Annotated[str, Field(pattern=r"^[a-zA-Z0-9_$]+$")]
    """Name of a callable value within the JS module."""
    data: str | None
    """JSON data given as argument to the function"""
    if_role: DisplayRole | None
    """Function is only called if the user has this role."""
    if_feedback_type: FeedbackType | None
    """Function is only called if the user is allowed to view this feedback type."""


class AttemptFile(BaseModel):
    name: str
    mime_type: str | None = None
    data: str


class AttemptUi(BaseModel):
    formulation: str
    """XHTML markup of the formulation part of the question."""
    general_feedback: str | None = None
    """XHTML markup of the general feedback part of the question."""
    specific_feedback: str | None = None
    """XHTML markup of the response-specific feedback part of the question."""
    right_answer: str | None = None
    """XHTML markup of the part of the question which explains the correct answer."""

    placeholders: dict[str, str] = {}
    """Names and values of the ``<?p`` placeholders that appear in content."""
    css_files: list[str] = []
    javascript_calls: list[JsModuleCall] = []
    files: dict[str, AttemptFile] = {}
    cache_control: CacheControl = CacheControl.PRIVATE_CACHE


class AttemptModel(Localized):
    variant: int
    ui: AttemptUi


class AttemptStartedModel(AttemptModel):
    attempt_state: str


class ScoringCode(Enum):
    AUTOMATICALLY_SCORED = "AUTOMATICALLY_SCORED"
    NEEDS_MANUAL_SCORING = "NEEDS_MANUAL_SCORING"
    RESPONSE_NOT_SCORABLE = "RESPONSE_NOT_SCORABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class ClassifiedResponse(BaseModel):
    subquestion_id: Annotated[str, Field(max_length=30, strict=True)]
    response_class: Annotated[str, Field(max_length=30, strict=True)]
    response: str
    score: float


class ScoredInputState(Enum):
    CORRECT = "CORRECT"
    CONSEQUENTIAL_SCORE = "CONSEQUENTIAL_SCORE"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    WRONG = "WRONG"


class ScoredInputModel(BaseModel):
    state: ScoredInputState
    score: float | None = None


class ScoredSubquestionModel(BaseModel):
    score: float | None = None
    score_adjusted: float | None = None
    scoring_code: ScoringCode | None = None
    response_summary: str
    response_class: str


class ScoreModel(BaseModel):
    scoring_state: str | None = None
    scoring_code: ScoringCode
    score: float | None
    """The score for this question attempt, must lie between the `score_min` and `score_max` set by the question."""
    score_adjusted: float | None
    scored_inputs: dict[str, ScoredInputModel] = {}
    """Maps input names to their individual scores."""
    scored_subquestions: dict[str, ScoredSubquestionModel] = {}
    """Maps subquestion IDs to their individual scores."""


class AttemptScoredModel(AttemptModel, ScoreModel):
    pass
