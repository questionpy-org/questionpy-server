import functools
from hashlib import sha256
from io import BytesIO
from json import loads, JSONDecodeError
from pathlib import Path
from typing import Optional, Union, Callable, Any, cast, Type, List, TYPE_CHECKING, Tuple, overload, Literal, NamedTuple

from aiohttp import BodyPartReader
from aiohttp.abc import Request
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPBadRequest, HTTPRequestEntityTooLarge, HTTPNotFound
from aiohttp.web_response import Response
from pydantic import BaseModel, ValidationError

from questionpy_common import constants

from questionpy_server.api.models import PackageQuestionStateNotFound, QuestionStateHash
from questionpy_server.cache import SizeError, FileLimitLRU
from questionpy_server.collector import PackageCollector
from questionpy_server.misc import get_route_model_param
from questionpy_server.types import RouteHandler, M

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer


def json_response(data: Union[List[BaseModel], BaseModel], status: int = 200) -> Response:
    """
    Creates a json response from a single BaseModel or a list of BaseModels.

    :param data: a BaseModel or a list of BaseModels
    :param status: HTTP status code
    :return: response object
    """

    if isinstance(data, list):
        json_list = f'[{",".join(x.json() for x in data)}]'
        return Response(text=json_list, status=status, content_type='application/json')
    return Response(text=data.json(), status=status, content_type='application/json')


def create_model_from_json(json: Union[object, str], param_class: Type[M]) -> M:
    """
    Creates a BaseModel from an object.

    :param json: object containing the parsed json
    :param param_class: BaseModel class
    :return: BaseModel
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
    """
    Reads a body part of a multipart/form-data request.

    :param part: body part
    :param max_size: maximum size of the body part
    :param calculate_hash: if True, returns a tuple of the body part and its hash
    :return: body part or tuple of body part and its hash
    """

    buffer = BytesIO()
    hash_object = sha256()

    size = 0

    while chunk := await part.read_chunk(size=262_144):
        # Check if size limit is exceeded.
        size += len(chunk)
        if size > max_size:
            raise HTTPRequestEntityTooLarge(max_size=max_size, actual_size=size)

        # Calculate hash.
        if calculate_hash:
            hash_object.update(chunk)

        # Write chunk to buffer.
        buffer.write(chunk)

    if calculate_hash:
        return HashContainer(data=buffer.getvalue(), hash=hash_object.hexdigest())
    return buffer.getvalue()


async def parse_form_data(request: Request) \
        -> Tuple[bytes, Optional[HashContainer], Optional[HashContainer]]:
    """
    Parses a multipart/form-data request.

    :param request: request to be parsed
    :return: tuple of main field, package, and question state
    """

    server: 'QPyServer' = request.app['qpy_server_app']
    main = package = question_state = None

    reader = await request.multipart()
    while part := await reader.next():
        if not isinstance(part, BodyPartReader):
            continue

        if part.name == 'main':
            main = await read_part(part, server.settings.webservice.max_bytes_main, calculate_hash=False)
        elif part.name == 'package':
            package = await read_part(part, server.settings.webservice.max_bytes_package, calculate_hash=True)
        elif part.name == 'question_state':
            question_state = await read_part(part, constants.MAX_BYTES_QUESTION_STATE, calculate_hash=True)

    if main is None:
        msg = "Multipart/form field 'main' is not set"
        web_logger.warning(msg)
        raise HTTPBadRequest(text=msg)

    return main, package, question_state


def get_or_save_data(location: Union[FileLimitLRU, PackageCollector], container: Optional[HashContainer],
                     hash_value: str) -> Optional[Path]:
    """
    Gets a file from the cache or saves it if it is not in the cache.
    :param location: cache or collector
    :param container: container with the file data and its hash
    :param hash_value: hash of the file
    :return: path to the file
    """

    try:
        if not container:
            path = location.get(hash_value)
        else:
            location = location.cache if isinstance(location, PackageCollector) else location
            path = location.put(container.hash, container.data)
    except SizeError as error:
        raise HTTPRequestEntityTooLarge(max_size=error.max_size, actual_size=error.actual_size,
                                        body=str(error)) from error
    except FileNotFoundError:
        return None
    return path


def ensure_package_and_question_state_exists(_func: Optional[RouteHandler] = None) \
        -> Union[RouteHandler, Callable[[RouteHandler], RouteHandler]]:
    """
    Decorator function used to ensure that the package and question type exists and that the json
    corresponds to the model given as a type annotation in func.

    :param _func: Control parameter; allows using the decorator with or without arguments.
            If this decorator is used with any arguments, this will always be the decorated function itself.
    """

    def decorator(function: RouteHandler) -> RouteHandler:
        """internal decorator function"""
        param_name, param_class = get_route_model_param(function, QuestionStateHash)

        @functools.wraps(function)
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            """Wrapper around the actual function call."""

            server: 'QPyServer' = request.app['qpy_server_app']
            package_hash: str = request.match_info['package_hash']

            if request.content_type == 'multipart/form-data':
                # Parse form-data.
                main, package, question_state = await parse_form_data(request)

                # Check if package hash matches.
                if package and package_hash != package.hash:
                    raise HTTPBadRequest(text=f'Package hash does not match: '
                                              f'{package_hash} != {package.hash}')

                # Create model from data.
                model = create_model_from_json(main.decode(), param_class)

                # Check if question state hash matches.
                if question_state and model.question_state_hash != question_state.hash:
                    raise HTTPBadRequest(text=f'Question state hash does not match: '
                                              f'{model.question_state_hash} != {question_state.hash}')

                # Get or save package and question_state.
                package_path = get_or_save_data(server.package_cache, package, package_hash)
                question_state_path = get_or_save_data(server.collector, question_state, model.question_state_hash)

                # Check if package and question_state exist.
                package_not_found = package_path is None
                question_state_not_found = question_state_path is None

                if package_not_found or question_state_not_found:
                    raise HTTPNotFound(
                        text=PackageQuestionStateNotFound(package_not_found=package_not_found,
                                                          question_state_not_found=question_state_not_found).json(),
                        content_type='application/json'
                    )

            elif request.content_type == 'application/json':
                try:
                    data = await request.json()
                    model = create_model_from_json(data, param_class)
                except JSONDecodeError as error:
                    web_logger.info('Invalid JSON in request')
                    raise HTTPBadRequest from error

                try:
                    package_path = server.collector.get(package_hash)
                    question_state_path = server.question_state_cache.get(model.question_state_hash)
                except FileNotFoundError as error:
                    # Check if package or question state does not exist.
                    package_not_found = not server.collector.contains(package_hash)
                    question_state_not_found = not server.question_state_cache.contains(model.question_state_hash)

                    raise HTTPNotFound(
                        text=PackageQuestionStateNotFound(package_not_found=package_not_found,
                                                          question_state_not_found=question_state_not_found).json(),
                        content_type='application/json'
                    ) from error

            else:
                web_logger.info('Wrong content type, json or multipart/form-data expected, got %s',
                                request.content_type)
                raise HTTPBadRequest

            kwargs[param_name] = model
            kwargs['package'] = package_path
            kwargs['question_state'] = question_state_path

            return await function(request, *args, **kwargs)

        return cast(RouteHandler, wrapper)

    if _func is None:
        return decorator
    return decorator(_func)
