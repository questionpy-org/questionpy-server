#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

__all__ = [
    "AttemptFile",
    "AttemptModel",
    "AttemptScoredModel",
    "AttemptUi",
    "BaseAttempt",
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
    css_files: list[str]
    files: dict[str, AttemptFile] = {}
    cache_control: CacheControl = CacheControl.PRIVATE_CACHE


class AttemptModel(BaseModel):
    variant: int
    ui: AttemptUi


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


class ScoreModel(BaseModel):
    scoring_state: str = "{}"
    scoring_code: ScoringCode
    score: float | None
    """The score for this question attempt, must lie between the `score_min` and `score_max` set by the question."""
    classification: Sequence[ClassifiedResponse] | None = None


class AttemptScoredModel(AttemptModel, ScoreModel):
    pass


class BaseAttempt(ABC):
    @abstractmethod
    def export_attempt_state(self) -> str:
        """Serialize this attempt's relevant data.

        A future call to :meth:`BaseQuestion.view_attempt` should result in an attempt object identical to the one which
        exported the state.
        """

    @abstractmethod
    def export(self) -> AttemptModel:
        """Get metadata about this attempt."""

    @abstractmethod
    def export_scored_attempt(self) -> AttemptScoredModel:
        """Score this attempt."""
