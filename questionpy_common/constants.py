#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import re
from typing import Final

from pydantic import ByteSize

# General.
KiB: Final[int] = 1024
MiB: Final[int] = 1024 * KiB
GiB: Final[int] = 1024 * MiB

# Request.
MAX_PACKAGE_SIZE: Final[ByteSize] = ByteSize(20 * MiB)
MAX_QUESTION_STATE_SIZE: Final[ByteSize] = ByteSize(2 * MiB)

MANIFEST_FILENAME: Final[str] = "qpy_manifest.json"
DIST_DIR: Final[str] = "dist"

MAX_QPY_DEPENDENCY_LEVELS: Final[int] = 5

MAX_MANIFEST_SIZE: Final[ByteSize] = ByteSize(1 * MiB)

FORM_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
FORM_REFERENCE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_]*|\.\.)(\[([a-zA-Z_][a-zA-Z0-9_]*|\.\.)?])*$"
)
