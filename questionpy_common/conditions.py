#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from abc import ABC
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class _BaseCondition(ABC, BaseModel):
    kind: str
    name: str


class IsChecked(_BaseCondition):
    kind: Literal["is_checked"] = "is_checked"


class IsNotChecked(_BaseCondition):
    kind: Literal["is_not_checked"] = "is_not_checked"


class Equals(_BaseCondition):
    kind: Literal["equals"] = "equals"
    value: str | int | bool


class DoesNotEqual(_BaseCondition):
    kind: Literal["does_not_equal"] = "does_not_equal"
    value: str | int | bool


class In(_BaseCondition):
    kind: Literal["in"] = "in"
    value: list[str | int | bool]


type Condition = Annotated[IsChecked | IsNotChecked | Equals | DoesNotEqual | In, Field(discriminator="kind")]
