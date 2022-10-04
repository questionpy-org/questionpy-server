import functools
from io import BytesIO
from json import loads, JSONDecodeError
from pathlib import Path
from typing import Optional, Union, Callable, Any, cast, Type, List, TYPE_CHECKING, Tuple

from aiohttp import BodyPartReader
from aiohttp.abc import Request
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPBadRequest, HTTPRequestEntityTooLarge, HTTPNotFound
from aiohttp.web_response import Response
from pydantic import BaseModel, ValidationError

from questionpy_common import constants

from questionpy_server.api.models import PackageQuestionStateNotFound, QuestionStateHash
from questionpy_server.cache import SizeError
from questionpy_server.collector import PackageNotFound
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


async def read_part(part: BodyPartReader, max_size: int) -> bytes:
    size = 0
    buffer = BytesIO()
    while True:
        chunk = await part.read_chunk()  # TODO: Make chunk size configurable? (default: 8 KB)
        if not chunk:
            break
        size += len(chunk)
        if size > max_size:
            raise HTTPRequestEntityTooLarge(max_size=max_size, actual_size=size)
        buffer.write(chunk)
    return buffer.getvalue()


async def parse_package_and_question_state_form_data(request: Request) \
        -> Tuple[str, Optional[bytes], Optional[str]]:

    server: 'QPyServer' = request.app['qpy_server_app']
    main = package = question_state = None

    reader = await request.multipart()
    while part := await reader.next():
        if not isinstance(part, BodyPartReader):
            continue

        if part.name == 'main':
            main_binary = await read_part(part, server.settings.webservice.max_bytes_main)
            main = main_binary.decode()
        elif part.name == 'package':
            package = await read_part(part, constants.MAX_BYTES_PACKAGE)
        elif part.name == 'question_state':
            question_state_binary = await read_part(part, constants.MAX_BYTES_QUESTION_STATE)
            question_state = question_state_binary.decode()

    if main is None:
        msg = "Multipart/form field 'main' is not set"
        web_logger.warning(msg)
        raise HTTPBadRequest(text=msg)

    return main, package, question_state


def get_package(server: 'QPyServer', package_hash: str, package: Optional[bytes]) -> Optional[Path]:
    """
    Saves a package on `server` or retrieves it from cache if `package` is None, and returns `Path` to the package.
    Raises `HTTPRequestEntityTooLarge` if the `package` is too big for the cache.

    :param server: server where to save the package on
    :param package_hash: hash of the package
    :param package: package to be saved on the server
    :return: `Path` of the package if it was created or found on the server, else `None`.
    """

    try:
        if not package:
            package_path = server.collector.get(package_hash)
        else:
            package_path = server.package_cache.put(package_hash, package)
    except SizeError as error:
        raise HTTPRequestEntityTooLarge(max_size=error.max_size, actual_size=error.actual_size,
                                        body=str(error)) from error
    except PackageNotFound:
        return None
    return package_path


def get_question_state(server: 'QPyServer', question_state_hash: str, question_state: Optional[str]) -> Optional[Path]:
    """
    Saves a question state on `server` or retrieves it from cache if `question_state` is None, and returns `Path` to
    the question state.
    Raises `SizeError` if the `question_state` is too big for the cache.

    :param server: server where to save the package on
    :param question_state_hash: hash of the question state
    :param question_state: question state to be saved on the server
    :return: `Path` of the question state if it was created or found on the server, else `None`.
    """

    try:
        if not question_state:
            question_state_path = server.question_state_cache.get(question_state_hash)
        else:
            question_state_path = server.question_state_cache.put(question_state_hash,
                                                                  question_state.encode())
    except SizeError as error:
        raise HTTPRequestEntityTooLarge(max_size=error.max_size, actual_size=error.actual_size,
                                        body=str(error)) from error
    except FileNotFoundError:
        return None
    return question_state_path


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
                main, package, question_state = await parse_package_and_question_state_form_data(request)

                # Create model from data.
                model = create_model_from_json(main, param_class)

                # Get or save package and question_state.
                package_path = get_package(server, package_hash, package)
                question_state_path = get_question_state(server, model.question_state_hash, question_state)

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
                except (FileNotFoundError, PackageNotFound) as error:
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
