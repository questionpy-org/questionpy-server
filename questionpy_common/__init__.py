#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import ABC, abstractmethod
from typing import Any, NamedTuple, Self

from pydantic import GetCoreSchemaHandler
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


class PackageNamespaceAndShortName(NamedTuple):
    """Tuple of namespace and short name, identifying any version of a specific package."""

    namespace: str
    short_name: str

    def __str__(self) -> str:
        return f"@{self.namespace}/{self.short_name}"

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Parse an NSSN in the same format as produced by `__str__`."""
        value = value.strip()
        if not value.startswith("@") or value.count("/") != 1:
            msg = f"Invalid package identifier (NSSN): '{value}'"
            raise ValueError(msg)

        ns, sn = value.removeprefix("@").split("/", maxsplit=1)
        return cls(ns, sn)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handle: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_before_validator_function(
            lambda obj: cls.from_string(obj) if isinstance(obj, str) else obj,
            handle(source_type),
            serialization=core_schema.to_string_ser_schema(),
        )
