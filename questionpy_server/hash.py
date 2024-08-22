#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from hashlib import sha256
from pathlib import Path
from typing import NamedTuple

from questionpy_common.constants import MiB


def calculate_hash(source: bytes | Path) -> str:
    """Calculates the sha256 of either bytes or a file.

    Args:
        source (Union[bytes, Path]) : bytes or path to file

    Returns:
        str: the sha256
    """
    sha = sha256()

    if isinstance(source, bytes):
        sha.update(source)
    else:
        with source.open("rb") as file:
            while chunk := file.read(5 * MiB):
                sha.update(chunk)

    return sha.hexdigest()


class HashContainer(NamedTuple):
    data: bytes
    hash: str
