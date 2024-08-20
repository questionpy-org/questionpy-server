#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Sequence
from hashlib import sha256
from io import BytesIO
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING, Literal, NamedTuple, overload

from aiohttp import BodyPartReader
from aiohttp.abc import Request
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPBadRequest, HTTPRequestEntityTooLarge
from aiohttp.web_response import Response
from aiohttp.web_response import json_response as aiohttp_json_response
from pydantic import BaseModel, ValidationError
from pydantic_core import to_jsonable_python

from questionpy_common import constants
from questionpy_common.constants import KiB
from questionpy_server.cache import SizeError
from questionpy_server.collector import PackageCollection
from questionpy_server.package import Package
from questionpy_server.types import M

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer


def json_response(data: Sequence[BaseModel] | BaseModel, status: int = 200) -> Response:
    """Creates a json response from a single BaseModel or a list of BaseModels.

    Args:
        data (Union[Sequence[BaseModel]): A BaseModel or a list of BaseModels.
        status (int): The HTTP status code.

    Returns:
        Response: A response object.
    """
    return aiohttp_json_response(data, status=status, dumps=lambda model: dumps(model, default=to_jsonable_python))


def create_model_from_json(json: object | str, param_class: type[M]) -> M:
    """Creates a BaseModel from an object.

    Args:
        json (Union[object, str]): object containing the parsed json
        param_class (type[M]): BaseModel class

    Returns:
        M: BaseModel
    """
    try:
        if isinstance(json, str):
            json = loads(json)
        model = param_class.model_validate(json)
    except ValidationError as error:
        web_logger.warning("JSON does not match model: %s", error)
        raise HTTPBadRequest from error
    except JSONDecodeError as error:
        web_logger.warning("Invalid JSON in request")
        raise HTTPBadRequest from error
    return model


class HashContainer(NamedTuple):
    data: bytes
    hash: str


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


async def parse_form_data(request: Request) -> tuple[bytes | None, HashContainer | None, bytes | None]:
    """Parses a multipart/form-data request.

    Args:
        request (Request): The request to be parsed.

    Returns:
        tuple of main field, package, and question state
    """
    server: QPyServer = request.app["qpy_server_app"]
    main = package = question_state = None

    reader = await request.multipart()
    while part := await reader.next():
        if not isinstance(part, BodyPartReader):
            continue

        if part.name == "main":
            main = await read_part(part, server.settings.webservice.max_main_size, calculate_hash=False)
        elif part.name == "package":
            package = await read_part(part, server.settings.webservice.max_package_size, calculate_hash=True)
        elif part.name == "question_state":
            question_state = await read_part(part, constants.MAX_QUESTION_STATE_SIZE, calculate_hash=False)

    return main, package, question_state


async def get_or_save_package(
    collection: PackageCollection, hash_value: str, container: HashContainer | None
) -> Package | None:
    """Gets a package from or saves it in the package collection.

    Args:
        collection (PackageCollection): package collection
        hash_value (str): The hash of the package.
        container (Optional[HashContainer]): container with the package data and its hash

    Returns:
        package
    """
    try:
        if not container:
            package = collection.get(hash_value)
        else:
            package = await collection.put(container)
    except SizeError as error:
        raise HTTPRequestEntityTooLarge(
            max_size=error.max_size, actual_size=error.actual_size, text=str(error)
        ) from error
    except FileNotFoundError:
        return None
    return package
