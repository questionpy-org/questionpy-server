#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import re
from enum import Enum
from keyword import iskeyword, issoftkeyword
from typing import Annotated

from pydantic import BaseModel, field_validator
from pydantic.fields import Field


class PackageType(str, Enum):
    LIBRARY = "LIBRARY"
    QUESTIONTYPE = "QUESTIONTYPE"
    QUESTION = "QUESTION"


# Defaults.
DEFAULT_NAMESPACE = "local"
DEFAULT_PACKAGETYPE = PackageType.QUESTIONTYPE

# Regular expressions.
RE_SEMVER = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
RE_API = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)$"
# The SemVer and Api version patterns are used on pydantic fields, which uses Rust regexes, so re.compiling them makes
# no sense. We match RE_VALID_CHARS_NAME in Python though, so here it does.
RE_VALID_CHARS_NAME = re.compile(r"^[a-z\d_]+$")

NAME_MAX_LENGTH = 127


# Validators.
def ensure_is_valid_name(name: str) -> str:
    """Ensures valid package name.

    Checks that `name`

      - contains only lowercase alphanumeric characters and underscores,
      - is 1 - 127 characters long,
      - does not start with a number,
      - is a valid Python identifier and
      - is NOT a Python keyword.

    Args:
      name: the name to be checked

    Returns:
      name

    Raises:
      ValueError: If the given name does not match the conditions.
    """
    length = len(name)

    if length < 1:
        msg = "can not be empty"
        raise ValueError(msg)
    if not RE_VALID_CHARS_NAME.match(name):
        msg = "can only contain lowercase alphanumeric characters and underscores"
        raise ValueError(msg)
    if length > NAME_MAX_LENGTH:
        msg = f"can have at most {NAME_MAX_LENGTH} characters"
        raise ValueError(msg)
    if name[0].isdigit():
        msg = "can not start with a digit"
        raise ValueError(msg)
    if not name.isidentifier():
        # This check should be redundant - we keep it just in case.
        msg = "is not a valid Python identifier"
        raise ValueError(msg)
    if iskeyword(name) or issoftkeyword(name) or name in {"_", "case", "match"}:
        msg = "can not be a Python keyword"
        raise ValueError(msg)

    return name


class Manifest(BaseModel):
    short_name: str
    namespace: str = DEFAULT_NAMESPACE
    version: Annotated[str, Field(pattern=RE_SEMVER)]
    api_version: Annotated[str, Field(pattern=RE_API)]
    author: str
    name: dict[str, str] = {}
    entrypoint: str | None = None
    url: str | None = None
    languages: set[str] = set()
    description: dict[str, str] = {}
    icon: str | None = None
    type: PackageType = DEFAULT_PACKAGETYPE
    license: str | None = None
    permissions: set[str] = set()
    tags: set[str] = set()
    requirements: str | list[str] | None = None

    @field_validator("short_name", "namespace")
    @classmethod
    def ensure_is_valid_name(cls, value: str) -> str:
        return ensure_is_valid_name(value)

    @property
    def identifier(self) -> str:
        return f"@{self.namespace}/{self.short_name}"
