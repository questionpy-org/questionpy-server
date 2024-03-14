#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

__all__ = [
    "AttemptModel",
    "AttemptScoredModel",
    "AttemptUi",
    "BaseAttempt",
    "CacheControl",
    "ClassifiedResponse",
    "ScoreModel",
    "ScoringCode",
    "UiFile",
]


class CacheControl(Enum):
    SHARED_CACHE = "SHARED_CACHE"
    PRIVATE_CACHE = "PRIVATE_CACHE"
    NO_CACHE = "NO_CACHE"


class UiFile(BaseModel):
    name: str
    data: str
    mime_type: str | None = None


class AttemptUi(BaseModel):
    content: str
    """X(H)ML markup of the question UI."""
    placeholders: dict[str, str] = {}
    """Names and values of the ``<?p`` placeholders that appear in content."""
    include_inline_css: str | None = None
    include_css_file: str | None = None
    cache_control: CacheControl = CacheControl.PRIVATE_CACHE
    files: list[UiFile] = []


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
    """The total score for this question attempt, as a fraction of the default mark set by the LMS."""
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
