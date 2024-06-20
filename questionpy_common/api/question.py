#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import abstractmethod
from enum import Enum
from typing import Annotated, Protocol

from pydantic import BaseModel, Field

from . import Localized
from .attempt import AttemptModel, AttemptScoredModel, AttemptStartedModel

__all__ = ["PossibleResponse", "QuestionInterface", "QuestionModel", "ScoringMethod", "SubquestionModel"]


class ScoringMethod(Enum):
    ALWAYS_MANUAL_SCORING_REQUIRED = "ALWAYS_MANUAL_SCORING_REQUIRED"
    AUTOMATICALLY_SCORABLE = "AUTOMATICALLY_SCORABLE"
    AUTOMATICALLY_SCORABLE_WITH_COUNTBACK = "AUTOMATICALLY_SCORABLE_WITH_COUNTBACK"


class PossibleResponse(BaseModel):
    response_class: Annotated[str, Field(max_length=30, strict=True)]
    score: float


class SubquestionModel(BaseModel):
    subquestion_id: Annotated[str, Field(max_length=30, strict=True)]
    score_max: float | None
    response_classes: list[PossibleResponse] | None


class QuestionModel(Localized):
    num_variants: Annotated[int, Field(ge=1, strict=True)] = 1
    score_min: float = 0
    """Lowest score used by this question."""
    score_max: float = 1
    """Highest score used by this question."""
    scoring_method: ScoringMethod
    penalty: float | None = None
    random_guess_score: float | None = None
    response_analysis_by_variant: bool = False

    subquestions: list[SubquestionModel] = []


class QuestionInterface(Protocol):
    @abstractmethod
    def start_attempt(self, variant: int) -> AttemptStartedModel:
        """Start an attempt at this question with the given variant.

        Args:
            variant: Not implemented.

        Returns:
            A :class:`BaseAttempt` object representing the attempt.
        """

    @abstractmethod
    def get_attempt(
        self, attempt_state: str, scoring_state: str | None = None, response: dict | None = None
    ) -> AttemptModel:
        """Create an attempt object for a previously started attempt.

        Args:
            attempt_state: The `attempt_state` attribute of an attempt which was previously returned by
                           :meth:`start_attempt`.
            scoring_state: Not implemented.
            response: The response currently entered by the student.

        Returns:
            A :class:`BaseAttempt` object which should be identical to the one which generated the given state(s).
        """

    @abstractmethod
    def score_attempt(
        self,
        attempt_state: str,
        scoring_state: str | None = None,
        response: dict | None = None,
        *,
        try_scoring_with_countback: bool = False,
        try_giving_hint: bool = False,
    ) -> AttemptScoredModel:
        """Create an attempt object for a previously started attempt.

        Args:
            attempt_state: The `attempt_state` attribute of an attempt which was previously returned by
                           :meth:`start_attempt`.
            scoring_state: Not implemented.
            response: The response currently entered by the student.
            try_scoring_with_countback: TBD
            try_giving_hint: TBD

        Returns:
            A :class:`BaseAttempt` object which should be identical to the one which generated the given state(s).
        """

    @abstractmethod
    def export_question_state(self) -> str:
        """Serialize this question's relevant data.

        A future call to :meth:`QuestionTypeInterface.create_question_from_state` should result in a question object
        identical to the one which exported the state.
        """

    @abstractmethod
    def export(self) -> QuestionModel:
        """Get metadata about this question."""
