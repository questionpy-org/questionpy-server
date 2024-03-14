#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import Annotated

from pydantic import PlainSerializer, PlainValidator
from questionpy_common.manifest import Manifest
from semver import VersionInfo as _Version
from typing_extensions import TypeAlias

SemVer: TypeAlias = Annotated[_Version, PlainValidator(_Version.parse), PlainSerializer(_Version.__str__)]


class ComparableManifest(Manifest):
    version: SemVer  # type: ignore[assignment]
