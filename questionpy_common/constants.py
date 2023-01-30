from typing import Final

from pydantic import ByteSize


# General.
KiB: Final[int] = 1024  # pylint: disable=invalid-name
MiB: Final[int] = 1024 * KiB  # pylint: disable=invalid-name

# Request.
MAX_PACKAGE_SIZE: Final[ByteSize] = ByteSize(20 * MiB)
MAX_QUESTION_STATE_SIZE: Final[ByteSize] = ByteSize(2 * MiB)
