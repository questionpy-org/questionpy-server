#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import (
    Mapping,
    Sequence,  # noqa: F401
)
from typing import (
    TypeAlias,
    Union,  # noqa: F401,
)

from pydantic import BaseModel
from typing_extensions import TypeAliasType


class Localized(BaseModel):
    lang: str


# "Regular" recursive type aliases break Pydantic: https://github.com/pydantic/pydantic/issues/8346
PlainValue: TypeAlias = TypeAliasType("PlainValue", "Union[None, int, str, bool, Sequence[PlainValue], PlainMapping]")
PlainMapping: TypeAlias = TypeAliasType("PlainMapping", Mapping[str, PlainValue])
