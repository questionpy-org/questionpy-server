#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from hashlib import sha256
from io import BytesIO
from typing import Literal, overload

import pydantic_core
from aiohttp import BodyPartReader
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPRequestEntityTooLarge
from aiohttp.web_response import Response

from questionpy_common.constants import KiB
from questionpy_server.hash import HashContainer


def pydantic_json_response(data: object, status: int = 200) -> Response:
    """Creates a json response from anything pydantic can dump."""
    return Response(body=pydantic_core.to_json(data), status=status, content_type="application/json", charset="utf-8")


@overload
async def read_part(part: BodyPartReader, max_size: int, *, calculate_hash: Literal[True]) -> HashContainer: ...


@overload
async def read_part(part: BodyPartReader, max_size: int, *, calculate_hash: Literal[False]) -> bytes: ...


async def read_part(part: BodyPartReader, max_size: int, *, calculate_hash: bool = False) -> HashContainer | bytes:
    """Reads a body part of a multipart/form-data request.

    Args:
        part (BodyPartReader): body part
        max_size (int): The maximum size of the body part.
        calculate_hash (bool): if True, returns a tuple of the body part and its hash

    Returns:
        body part or tuple of body part and its hash
    """
    buffer = BytesIO()
    hash_object = sha256()

    size = 0

    while chunk := await part.read_chunk(size=256 * KiB):
        # Check if size limit is exceeded.
        size += len(chunk)
        if size > max_size:
            msg = f"Size limit of {max_size} exceeded for field '{part.name}'"
            web_logger.warning(msg)
            raise HTTPRequestEntityTooLarge(text=msg, max_size=max_size, actual_size=size)

        # Calculate hash.
        if calculate_hash:
            hash_object.update(chunk)

        # Write chunk to buffer.
        buffer.write(chunk)

    if calculate_hash:
        return HashContainer(data=buffer.getvalue(), hash=hash_object.hexdigest())
    return buffer.getvalue()
