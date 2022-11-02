from abc import ABC
from typing import Any, Literal

from pydantic import BaseModel


class Condition(ABC, BaseModel):
    kind: str = ""
    name: str


class ConditionWithValue(Condition, ABC):
    value: Any


class IsChecked(Condition):
    kind: Literal["is_checked"] = "is_checked"


class IsNotChecked(Condition):
    kind: Literal["is_not_checked"] = "is_not_checked"


class Equals(ConditionWithValue):
    kind: Literal["equals"] = "equals"


class DoesNotEqual(ConditionWithValue):
    kind: Literal["does_not_equal"] = "does_not_equal"


class In(ConditionWithValue):
    kind: Literal["in"] = "in"
