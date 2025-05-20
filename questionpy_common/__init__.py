#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import ABC, abstractmethod

from pydantic_core import CoreSchema, core_schema


class TranslatableString(ABC):
    """Protocol for strings which may be lazily retrieved, such as deferred translations."""

    @abstractmethod
    def __str__(self) -> str:
        """Translate this string."""

    @classmethod
    def __get_pydantic_core_schema__(cls, *_: object) -> CoreSchema:
        # Never convert anything to a TranslatableString, but accept existing instances, and serialize by using str().
        return core_schema.is_instance_schema(cls, serialization=core_schema.to_string_ser_schema())


TranslatableString.register(str)
