#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import re
from enum import StrEnum
from keyword import iskeyword, issoftkeyword
from typing import Annotated, NewType

from pydantic import (
    AfterValidator,
    BaseModel,
    ByteSize,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    conset,
    field_validator,
)
from pydantic.fields import Field

from questionpy_common.constants import ENVIRONMENT_VARIABLE_REGEX


class PackageType(StrEnum):
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

    Checks that `name` follows the [naming rules](../../../documentation/configuration.md#short_name).

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
    if iskeyword(name) or issoftkeyword(name):
        msg = "can not be a Python keyword"
        raise ValueError(msg)

    return name


Bcp47LanguageTag = NewType("Bcp47LanguageTag", str)


type Namespace = Annotated[str, AfterValidator(ensure_is_valid_name)]
type ShortName = Namespace


class PartialPackagePermissions(BaseModel):
    cpus: int | None = None
    memory: ByteSize | None = None
    request_timeout: PositiveInt | None = None
    bootstrap_timeout: PositiveInt | None = None
    main_process_execution_modes: conset(str, min_length=1) | None = None  # type: ignore[valid-type]
    lms_attributes: set[str] | None = None


type EnvironmentVariableName = Annotated[str, Field(pattern=f"^{ENVIRONMENT_VARIABLE_REGEX}$")]


class SourceManifest(BaseModel):
    """Represents the fields in a package source directory.

    These fields are valid inside a package's configuration file.
    """

    short_name: ShortName
    namespace: Namespace = DEFAULT_NAMESPACE
    version: Annotated[str, Field(pattern=RE_SEMVER)]
    api_version: Annotated[str, Field(pattern=RE_API)]
    author: str
    name: dict[Bcp47LanguageTag, Annotated[str, StringConstraints(min_length=1)]] = Field(min_length=1)
    entrypoint: str | None = None
    url: str | None = None
    languages: list[Bcp47LanguageTag] = Field(min_length=1)
    """Languages supported by the package, in BCP 47 format.

    The first entry should by the language that the package is written in, i.e. the language used when no translation is
    done. If the package does not support localization, that should be the only entry.
    """
    description: dict[Bcp47LanguageTag, str] = {}
    icon: str | None = None
    type: PackageType = DEFAULT_PACKAGETYPE
    license: str | None = None
    permissions: PartialPackagePermissions | None = None
    environment_variables: set[EnvironmentVariableName] | None = None
    tags: set[str] = set()
    requirements: str | list[str] | None = None

    @field_validator("languages", "name")
    @classmethod
    def ensure_contains_english_translation(
        cls, value: list[Bcp47LanguageTag] | dict[Bcp47LanguageTag, str]
    ) -> list[Bcp47LanguageTag] | dict[Bcp47LanguageTag, str]:
        if Bcp47LanguageTag("en") not in value:
            msg = "must contain an english translation"
            raise ValueError(msg)
        return value

    @property
    def identifier(self) -> str:
        return f"@{self.namespace}/{self.short_name}"


class PackageFile(BaseModel):
    """Represents a static file included in a built package."""

    mime_type: str | None
    size: int


class DistStaticQPyDependency(BaseModel):
    dir_name: str
    """Name (without `dist/dependencies/qpy/`) of the directory the dependency package contents reside in."""
    hash: str
    """Hash of the ZIP package whose contents lie in `dir_name`."""


type DistQPyDependency = DistStaticQPyDependency


class DistDependencies(BaseModel):
    qpy: list[DistQPyDependency] = []


class Manifest(SourceManifest):
    """Represents a package manifest.

    Contains fields valid in a pre-built package manifest.
    """

    static_files: dict[str, PackageFile] = {}

    dependencies: DistDependencies = DistDependencies()

    state_version: NonNegativeInt = 0
    possible_side_migrations: dict[Namespace, dict[ShortName, set[NonNegativeInt]]] = {}
