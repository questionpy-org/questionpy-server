#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from hashlib import file_digest, sha256
from io import BufferedIOBase, RawIOBase
from pathlib import Path
from typing import NamedTuple


def calculate_hash(source: bytes | Path | RawIOBase | BufferedIOBase) -> str:
    """Calculates the sha256 of either bytes or a file.

    Args:
        source: bytes, already opened file, or path to a file
    """
    if isinstance(source, bytes):
        sha = sha256()
        sha.update(source)
    elif isinstance(source, Path):
        with source.open("rb") as file:
            sha = file_digest(file, sha256)
    else:
        sha = file_digest(source, sha256)

    return sha.hexdigest()


class HashContainer(NamedTuple):
    data: bytes
    hash: str
