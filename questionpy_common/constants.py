from typing import Final

from questionpy_common.misc import Size, SizeUnit

# Request.
MAX_BYTES_PACKAGE: Final[Size] = Size(20, SizeUnit.MiB)
MAX_BYTES_QUESTION_STATE: Final[Size] = Size(2, SizeUnit.MiB)
