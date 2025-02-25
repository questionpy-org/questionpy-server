#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from pydantic_core import CoreSchema, core_schema


@runtime_checkable
class TranslatableString(Protocol):
    """Protocol for strings which may be lazily retrieved, such as deferred translations."""

    def __str__(self) -> str:
        """Translate this string."""

    def format(self, *args: object, **kwargs: object) -> "str | TranslatableString":
        """Perform the same formatting as [`str.format`][], possibly lazily."""

    def format_map(self, mapping: Mapping[str, object]) -> "str | TranslatableString":
        """Perform the same formatting as [`str.format_map`][], possibly lazily."""

    @classmethod
    def __get_pydantic_core_schema__(cls, *_: object) -> CoreSchema:
        # Never convert anything to a TranslatableString, but accept existing instances, and serialize by using str().
        return core_schema.is_instance_schema(cls, serialization=core_schema.to_string_ser_schema())
