#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import Final

from pydantic import ByteSize

# General.
KiB: Final[int] = 1024
MiB: Final[int] = 1024 * KiB
GiB: Final[int] = 1024 * MiB

# Request.
MAX_PACKAGE_SIZE: Final[ByteSize] = ByteSize(20 * MiB)
MAX_QUESTION_STATE_SIZE: Final[ByteSize] = ByteSize(2 * MiB)

MANIFEST_FILENAME = "qpy_manifest.json"
DIST_DIR = "dist"

MAX_QPY_DEPENDENCY_LEVELS = 5
