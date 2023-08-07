from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class ScoringMethod(Enum):
    ALWAYS_MANUAL_SCORING_REQUIRED = 'ALWAYS_MANUAL_SCORING_REQUIRED'
    AUTOMATICALLY_SCORABLE = 'AUTOMATICALLY_SCORABLE'
    AUTOMATICALLY_SCORABLE_WITH_COUNTBACK = 'AUTOMATICALLY_SCORABLE_WITH_COUNTBACK'


class PossibleResponse(BaseModel):
    response_class: Annotated[str, Field(max_length=30, strict=True)]
    score: float


class SubquestionModel(BaseModel):
    subquestion_id: Annotated[str, Field(max_length=30, strict=True)]
    score_max: Optional[float]
    response_classes: Optional[list[PossibleResponse]]


class QuestionModel(BaseModel):
    num_variants: Annotated[int, Field(ge=1, strict=True)] = 1
    score_min: float = 0
    score_max: float = 1
    scoring_method: ScoringMethod
    penalty: Optional[float] = None
    random_guess_score: Optional[float] = None
    response_analysis_by_variant: bool = True

    subquestions: Optional[list[SubquestionModel]] = None


class CacheControl(Enum):
    SHARED_CACHE = "SHARED_CACHE"
    PRIVATE_CACHE = "PRIVATE_CACHE"
    NO_CACHE = "NO_CACHE"


class UiFile(BaseModel):
    name: str
    data: str
    mime_type: Optional[str] = None


class AttemptUi(BaseModel):
    content: str
    """X(H)ML markup of the question UI."""
    parameters: dict[str, str] = {}
    """Values that ``<?p`` placeholders in the content will be replaced with during rendering."""
    include_inline_css: Optional[str] = None
    include_css_file: Optional[str] = None
    cache_control: CacheControl = CacheControl.PRIVATE_CACHE
    files: list[UiFile] = []


class AttemptModel(BaseModel):
    variant: int
    ui: AttemptUi
