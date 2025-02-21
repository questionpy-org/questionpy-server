#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import Mapping
from typing import Annotated, Protocol, runtime_checkable

from pydantic import InstanceOf, PlainSerializer


@runtime_checkable
class _TranslatableString(Protocol):
    def __str__(self) -> str:
        """Translate this string."""

    def format(self, *args: object, **kwargs: object) -> "str | TranslatableString":
        """Perform the same formatting as [str.format][], possibly lazily."""

    def format_map(self, mapping: Mapping[str, object]) -> "str | TranslatableString":
        """Perform the same formatting as [str.format_map][], possibly lazily."""


TranslatableString = Annotated[_TranslatableString, InstanceOf(), PlainSerializer(str, return_type=str)]
