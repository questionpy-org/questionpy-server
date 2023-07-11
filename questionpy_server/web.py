#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import functools
from hashlib import sha256
from io import BytesIO
from json import loads, JSONDecodeError
from pathlib import Path
from typing import Optional, Union, Callable, Any, cast, Type, TYPE_CHECKING, overload, Literal, NamedTuple, Sequence

from aiohttp import BodyPartReader
from aiohttp.abc import Request
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPBadRequest, HTTPRequestEntityTooLarge, HTTPNotFound, HTTPUnsupportedMediaType
from aiohttp.web_response import Response
from pydantic import BaseModel, ValidationError
from questionpy_common import constants
from questionpy_common.constants import KiB

from questionpy_server.api.models import PackageQuestionStateNotFound, QuestionStateHash, OptionalQuestionStateHash
from questionpy_server.cache import SizeError, FileLimitLRU
from questionpy_server.collector import PackageCollection
from questionpy_server.misc import get_route_model_param
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
    return Response(text=data.json(), status=status, content_type='application/json')


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
        model = param_class.parse_obj(json)
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
        -> tuple[bytes, Optional[HashContainer], Optional[HashContainer]]:
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
            question_state = await read_part(part, constants.MAX_QUESTION_STATE_SIZE, calculate_hash=True)

    if main is None:
        msg = "Multipart/form field 'main' is not set"
        web_logger.warning(msg)
        raise HTTPBadRequest(text=msg)

    return main, package, question_state


async def get_or_save_with_cache(cache: FileLimitLRU, hash_value: str, container: Optional[HashContainer]) \
        -> Optional[Path]:
    """Gets a file from the cache or saves it if it is not in the cache.

    Args:
        cache (FileLimitLRU): The cache.
        hash_value (str): The hash of the file.
        container (Optional[HashContainer]): container with the file data and its hash

    Returns:
        The path to the file.
    """

    try:
        if not container:
            path = cache.get(hash_value)
        else:
            path = await cache.put(container.hash, container.data)
    except SizeError as error:
        raise HTTPRequestEntityTooLarge(max_size=error.max_size, actual_size=error.actual_size,
                                        text=str(error)) from error
    except FileNotFoundError:
        return None
    return path


def get_from_cache(cache: FileLimitLRU, hash_value: str) -> Optional[Path]:
    """Gets a file from the cache.

    Args:
        cache (FileLimitLRU): The cache.
        hash_value (str): The hash of the file.

    Returns:
        The path to the file.
    """

    try:
        path = cache.get(hash_value)
    except FileNotFoundError:
        return None
    return path


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


async def get_data_package(collection: PackageCollection, hash_value: str) -> Optional[Package]:
    """Gets a package from the collection.

    Args:
        collection (PackageCollection): package collection
        hash_value (str): The hash of the package.

    Returns:
        package
    """

    try:
        return collection.get(hash_value)
    except FileNotFoundError:
        return None


class BodyContents(NamedTuple):
    main: bytes
    package: HashContainer
    question_state: Optional[HashContainer]


def ensure_package_and_question_state_exists(_func: Optional[RouteHandler] = None) \
        -> Union[RouteHandler, Callable[[RouteHandler], RouteHandler]]:
    """Decorator function used to ensure that the package and question type exists and that the json
    corresponds to the model given as a type annotation in func.

    Args:
        _func (Optional[RouteHandler]): Control parameter; allows using the decorator with or without arguments.
            If this decorator is used with any arguments, this will always be the decorated function itself.
            (Default value = None)
    """

    def decorator(function: RouteHandler) -> RouteHandler:
        """Internal decorator function."""
        param_name, param_class = get_route_model_param(function, OptionalQuestionStateHash)
        require_question_state = issubclass(param_class, QuestionStateHash)

        @functools.wraps(function)
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            """Wrapper around the actual function call."""

            server: 'QPyServer' = request.app['qpy_server_app']
            package_hash: str = request.match_info['package_hash']

            if request.content_type == 'multipart/form-data':
                main, sent_package, sent_question_state = await parse_form_data(request)
            elif request.content_type == 'application/json':
                main, sent_package, sent_question_state = await request.read(), None, None
            else:
                web_logger.info('Wrong content type, json or multipart/form-data expected, got %s',
                                request.content_type)
                raise HTTPUnsupportedMediaType

            model = create_model_from_json(main.decode(), param_class)

            # Check if package hash matches.
            if sent_package and package_hash != sent_package.hash:
                msg = f'Package hash does not match: {package_hash} != {sent_package.hash}'
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            # Check if required question state was not provided
            if require_question_state and not model.question_state_hash:
                raise HTTPBadRequest(text="Question state is required")

            # Check if question state hash matches.
            if sent_question_state and model.question_state_hash != sent_question_state.hash:
                msg = f'Question state hash does not match: {model.question_state_hash} != {sent_question_state.hash}'
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            package = await get_or_save_package(server.package_collection, package_hash, sent_package)
            question_state_path = None
            if model.question_state_hash:
                question_state_path = await get_or_save_with_cache(server.question_state_cache,
                                                                   model.question_state_hash, sent_question_state)

            package_not_found = package is None
            question_state_not_found = question_state_path is None and model.question_state_hash is not None
            if package_not_found or question_state_not_found:
                raise HTTPNotFound(
                    text=PackageQuestionStateNotFound(package_not_found=package_not_found,
                                                      question_state_not_found=question_state_not_found).json(),
                    content_type='application/json'
                )

            kwargs[param_name] = model
            kwargs['package'] = package
            kwargs['question_state'] = question_state_path

            return await function(request, *args, **kwargs)

        return cast(RouteHandler, wrapper)

    if _func is None:
        return decorator
    return decorator(_func)


def ensure_package_exists(_func: Optional[RouteHandler] = None, required_hash: bool = True) \
        -> Union[RouteHandler, Callable[[RouteHandler], RouteHandler]]:
    def decorator(function: RouteHandler) -> RouteHandler:
        """Internal decorator function."""

        @functools.wraps(function)
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            """Wrapper around the actual function call."""

            if request.content_type != 'multipart/form-data':
                web_logger.info('Wrong content type, json or multipart/form-data expected, got %s',
                                request.content_type)
                raise HTTPBadRequest

            server: 'QPyServer' = request.app['qpy_server_app']
            package_container: Optional[HashContainer] = None

            reader = await request.multipart()
            while part := await reader.next():
                if not isinstance(part, BodyPartReader):
                    continue
                if part.name == 'package':
                    package_container = await read_part(part, server.settings.webservice.max_package_size,
                                                        calculate_hash=True)
                    break

            if not package_container:
                msg = 'No package found in multipart/form-data'
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            package_hash: str = ""
            if required_hash:
                package_hash = request.match_info['package_hash']
                if package_hash != package_container.hash:
                    msg = f'Package hash does not match: {package_hash} != {package_container.hash}'
                    web_logger.warning(msg)
                    raise HTTPBadRequest(text=msg)

            package = await get_or_save_package(server.package_collection, package_hash, package_container)
            kwargs['package'] = package

            return await function(request, *args, **kwargs)

        return cast(RouteHandler, wrapper)

    if _func is None:
        return decorator
    return decorator(_func)
