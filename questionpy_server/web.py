#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import functools
from hashlib import sha256
from io import BytesIO
from json import loads, JSONDecodeError
from typing import Optional, Union, Callable, Any, cast, Type, TYPE_CHECKING, overload, Literal, NamedTuple, Sequence, \
    get_type_hints

from aiohttp import BodyPartReader
from aiohttp.abc import Request
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPBadRequest, HTTPRequestEntityTooLarge, HTTPNotFound, HTTPUnsupportedMediaType
from aiohttp.web_response import Response
from pydantic import BaseModel, ValidationError
from questionpy_common import constants
from questionpy_common.constants import KiB

from questionpy_server.api.models import PackageNotFound, MainBaseModel
from questionpy_server.cache import SizeError
from questionpy_server.collector import PackageCollection
from questionpy_server.package import Package
from questionpy_server.types import RouteHandler, M

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer


def json_response(data: Union[Sequence[BaseModel], BaseModel], status: int = 200) -> Response:
    """Creates a json response from a single BaseModel or a list of BaseModels.

    Args:
        data (Union[Sequence[BaseModel]): A BaseModel or a list of BaseModels.
        status (int): The HTTP status code.

    Returns:
        Response: A response object.
    """

    if isinstance(data, Sequence):
        json_list = f'[{",".join(x.json() for x in data)}]'
        return Response(text=json_list, status=status, content_type='application/json')
    return Response(text=data.model_dump_json(), status=status, content_type='application/json')


def create_model_from_json(json: Union[object, str], param_class: Type[M]) -> M:
    """Creates a BaseModel from an object.

    Args:
        json (Union[object, str]): object containing the parsed json
        param_class (Type[M]): BaseModel class

    Returns:
        M: BaseModel
    """

    try:
        if isinstance(json, str):
            json = loads(json)
        model = param_class.model_validate(json)
    except ValidationError as error:
        web_logger.warning('JSON does not match model: %s', error)
        raise HTTPBadRequest from error
    except JSONDecodeError as error:
        web_logger.warning('Invalid JSON in request')
        raise HTTPBadRequest from error
    return model


class HashContainer(NamedTuple):
    data: bytes
    hash: str


@overload
async def read_part(part: BodyPartReader, max_size: int, calculate_hash: Literal[True]) -> HashContainer:
    ...


@overload
async def read_part(part: BodyPartReader, max_size: int, calculate_hash: Literal[False]) -> bytes:
    ...


async def read_part(part: BodyPartReader, max_size: int, calculate_hash: bool = False) -> Union[HashContainer, bytes]:
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


async def parse_form_data(request: Request) \
        -> tuple[Optional[bytes], Optional[HashContainer], Optional[bytes]]:
    """Parses a multipart/form-data request.

    Args:
        request (Request): The request to be parsed.

    Returns:
        tuple of main field, package, and question state
    """

    server: 'QPyServer' = request.app['qpy_server_app']
    main = package = question_state = None

    reader = await request.multipart()
    while part := await reader.next():
        if not isinstance(part, BodyPartReader):
            continue

        if part.name == 'main':
            main = await read_part(part, server.settings.webservice.max_main_size, calculate_hash=False)
        elif part.name == 'package':
            package = await read_part(part, server.settings.webservice.max_package_size, calculate_hash=True)
        elif part.name == 'question_state':
            question_state = await read_part(part, constants.MAX_QUESTION_STATE_SIZE, calculate_hash=False)

    return main, package, question_state


async def get_or_save_package(collection: PackageCollection, hash_value: str, container: Optional[HashContainer]) \
        -> Optional[Package]:
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
        raise HTTPRequestEntityTooLarge(max_size=error.max_size, actual_size=error.actual_size,
                                        text=str(error)) from error
    except FileNotFoundError:
        return None
    return package


def ensure_package_and_question_state_exist(_func: Optional[RouteHandler] = None) \
        -> Union[RouteHandler, Callable[[RouteHandler], RouteHandler]]:
    """Decorator function used to ensure that the package and question state exist (if needed by func) and that the json
    corresponds to the model given as a type annotation in func.

    This decorator assumes that:
      * func may want an argument named 'data' (with a subclass of MainBaseModel)
      * func may want an argument named 'question_state' (bytes or Optional[bytes])
      * every func wants a package with an argument named 'package'

    Args:
        _func (Optional[RouteHandler]): Control parameter; allows using the decorator with or without arguments.
            If this decorator is used with any arguments, this will always be the decorated function itself.
            (Default value = None)
    """

    def decorator(function: RouteHandler) -> RouteHandler:
        """Internal decorator function."""

        type_hints = get_type_hints(function)
        question_state_type = type_hints.get('question_state')
        takes_question_state = question_state_type is not None
        require_question_state = question_state_type is bytes
        main_part_json_model: Optional[Type[MainBaseModel]] = type_hints.get('data')

        if main_part_json_model:
            assert issubclass(main_part_json_model, MainBaseModel), \
                f"Parameter 'data' of function {function.__name__} has unexpected type."

        @functools.wraps(function)
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            """Wrapper around the actual function call."""

            server: 'QPyServer' = request.app['qpy_server_app']
            package_hash: str = request.match_info.get('package_hash', '')

            if request.content_type == 'multipart/form-data':
                main, sent_package, sent_question_state = await parse_form_data(request)
            elif request.content_type == 'application/json':
                main, sent_package, sent_question_state = await request.read(), None, None
            else:
                web_logger.info('Wrong content type, multipart/form-data expected, got %s',
                                request.content_type)
                raise HTTPUnsupportedMediaType

            if main_part_json_model:
                if main is None:
                    msg = "Multipart/form-data field 'main' is not set"
                    web_logger.warning(msg)
                    raise HTTPBadRequest(text=msg)

                model = create_model_from_json(main.decode(), main_part_json_model)
                kwargs['data'] = model

            # Check if func wants a question state and if it is provided.
            if takes_question_state:
                if require_question_state and sent_question_state is None:
                    msg = "Multipart/form-data field 'question_state' is not set"
                    web_logger.warning(msg)
                    raise HTTPBadRequest(text=msg)
                kwargs['question_state'] = sent_question_state

            # Check if a package is provided and if it matches the optional hash given in the URL.
            if sent_package and package_hash and package_hash != sent_package.hash:
                msg = f'Package hash does not match: {package_hash} != {sent_package.hash}'
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            package = await get_or_save_package(server.package_collection, package_hash, sent_package)
            if package is None:
                if package_hash:
                    raise HTTPNotFound(
                        text=PackageNotFound(package_not_found=True).model_dump_json(),
                        content_type='application/json'
                    )

                msg = 'No package found in multipart/form-data'
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            kwargs['package'] = package
            return await function(request, *args, **kwargs)

        return cast(RouteHandler, wrapper)

    if _func is None:
        return decorator
    return decorator(_func)
