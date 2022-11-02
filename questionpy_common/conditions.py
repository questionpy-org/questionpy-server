from abc import ABC
from typing import Literal, Union, List

from pydantic import BaseModel


class Condition(ABC, BaseModel):
    kind: str = ""
    name: str


class IsChecked(Condition):
    kind: Literal["is_checked"] = "is_checked"


class IsNotChecked(Condition):
    kind: Literal["is_not_checked"] = "is_not_checked"


class Equals(Condition):
    kind: Literal["equals"] = "equals"
    value: Union[str, int, float]


class DoesNotEqual(Condition):
    kind: Literal["does_not_equal"] = "does_not_equal"
    value: Union[str, int, float]


class In(Condition):
    kind: Literal["in"] = "in"
    value: List[Union[str, int, float]]
