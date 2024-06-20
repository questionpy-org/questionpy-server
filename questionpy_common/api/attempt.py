#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from enum import Enum
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
    "ScoreModel",
    "ScoringCode",
]


class CacheControl(Enum):
    SHARED_CACHE = "SHARED_CACHE"
    PRIVATE_CACHE = "PRIVATE_CACHE"
    NO_CACHE = "NO_CACHE"


class AttemptFile(BaseModel):
    name: str
    mime_type: str | None = None
    data: str


class AttemptUi(BaseModel):
    formulation: str
    """X(H)ML markup of the formulation part of the question."""
    general_feedback: str | None = None
    """X(H)ML markup of the general feedback part of the question."""
    specific_feedback: str | None = None
    """X(H)ML markup of the response-specific feedback part of the question."""
    right_answer: str | None = None
    """X(H)ML markup of the part of the question which explains the correct answer."""

    placeholders: dict[str, str] = {}
    """Names and values of the ``<?p`` placeholders that appear in content."""
    css_files: list[str] = []
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
    score_max: float | None = None
    specific_feedback: str | None = None
    right_answer: str | None = None


class ScoredSubquestionModel(BaseModel):
    score: float | None = None
    score_final: float | None = None
    scoring_code: ScoringCode | None = None
    response_summary: str
    response_class: str


class ScoreModel(BaseModel):
    scoring_state: str | None = None
    scoring_code: ScoringCode
    score: float | None
    """The score for this question attempt, must lie between the `score_min` and `score_max` set by the question."""
    score_final: float | None
    scored_inputs: dict[str, ScoredInputModel] = {}
    """Maps input names to their individual scores."""
    scored_subquestions: dict[str, ScoredSubquestionModel] = {}
    """Maps subquestion IDs to their individual scores."""


class AttemptScoredModel(AttemptModel, ScoreModel):
    pass
