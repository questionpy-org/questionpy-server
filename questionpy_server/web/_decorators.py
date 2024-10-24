#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import Parameter
from typing import Concatenate, NamedTuple, ParamSpec, TypeAlias, TypeVar

from aiohttp import BodyPartReader, web
from aiohttp.log import web_logger
from pydantic import BaseModel, ValidationError

from questionpy_common import constants
from questionpy_server.cache import CacheItemTooLargeError
from questionpy_server.hash import HashContainer
from questionpy_server.models import MainBaseModel
from questionpy_server.package import Package
from questionpy_server.web._utils import read_part
from questionpy_server.web.app import QPyServer
from questionpy_server.web.errors import (
    InvalidPackageError,
    InvalidRequestError,
)

_P = ParamSpec("_P")
_HandlerFunc: TypeAlias = Callable[Concatenate[web.Request, _P], Awaitable[web.StreamResponse]]


def ensure_required_parts(handler: _HandlerFunc) -> _HandlerFunc:
    """Decorator passing the main body, package and question state into handler method if necessary.

    Composes the functionality of [ensure_package][], [ensure_question_state][] and [ensure_main_body][] if their
    respective parameters exist on the handler function.
    """
    signature = inspect.signature(handler)

    main_body_param = _get_main_body_param(handler, signature)
    question_state_param = signature.parameters.get("question_state", None)
    package_param = _get_package_param(handler, signature)

    if main_body_param:
        handler = ensure_main_body(handler, param=main_body_param)

    if question_state_param:
        handler = ensure_question_state(handler, param=question_state_param)

    if package_param:
        handler = ensure_package(handler, param=package_param)

    return handler


def ensure_package(handler: _HandlerFunc, *, param: inspect.Parameter | None = None) -> _HandlerFunc:
    """Decorator that ensures that the package needed by the handler is present and passes it in.

    The handler function must declare exactly one parameter of type [Package][].
    """
    if not param:
        signature = inspect.signature(handler)
        param = _get_package_param(handler, signature)

    if not param:
        msg = f"Handler '{handler.__name__}' does not have a package param but is decorated with ensure_package."
        raise TypeError(msg)

    @wraps(handler)
    async def wrapper(request: web.Request, *args: _P.args, **kwargs: _P.kwargs) -> web.StreamResponse:
        kwargs[param.name] = await _get_package_from_request(request)
        return await handler(request, *args, **kwargs)

    return wrapper


def ensure_question_state(handler: _HandlerFunc, *, param: inspect.Parameter | None = None) -> _HandlerFunc:
    """Decorator that ensures that the question state, if needed by the handler, is present and passes it in.

    The handler function must declare exactly one parameter named `question_state`. The question state is considered
    optional the that parameter has a default value. (Which is usually `None`.) If the parameter has no default value
    but the request doesn't include the question state, [QuestionStateMissingError][] will be raised, leading to a bad
    request response.
    """
    if not param:
        signature = inspect.signature(handler)
        param = signature.parameters.get("question_state", None)

    if not param:
        msg = (
            f"Handler '{handler.__name__}' does not have a question state param but is decorated with "
            f"ensure_question_state."
        )
        raise TypeError(msg)

    @wraps(handler)
    async def wrapper(request: web.Request, *args: _P.args, **kwargs: _P.kwargs) -> web.StreamResponse:
        parts = await _read_body_parts(request)

        if parts.question_state is not None:
            kwargs[param.name] = parts.question_state
        elif param.default is Parameter.empty:
            _msg = "A question state part is required but was not provided."
            raise InvalidRequestError(reason=_msg, temporary=False)

        return await handler(request, *args, **kwargs)

    return wrapper


def ensure_main_body(handler: _HandlerFunc, *, param: inspect.Parameter | None = None) -> _HandlerFunc:
    """Decorator that ensures that the main body is present, parses it, and passes it in.

    The handler function must declare exactly one parameter with a subtype of [MainBaseModel][]. The request may:
    - use Content-Type `application/json`, in which case the entire body is considered the main body, or
    - use Content-Type `multipart/form-data`, in which case a part named `main` must exist, which is then considered the
      main body.
    """
    if not param:
        signature = inspect.signature(handler)
        param = _get_main_body_param(handler, signature)

    if not param:
        msg = (
            f"Handler '{handler.__name__}' does not have a MainBaseModel param but is decorated with "
            f"ensure_main_body."
        )
        raise TypeError(msg)

    @wraps(handler)
    async def wrapper(request: web.Request, *args: _P.args, **kwargs: _P.kwargs) -> web.StreamResponse:
        parts = await _read_body_parts(request)

        if parts.main is None:
            _msg = "The main body is required but was not provided."
            raise InvalidRequestError(reason=_msg, temporary=False)

        kwargs[param.name] = _validate_from_http(parts.main, param.annotation)
        return await handler(request, *args, **kwargs)

    return wrapper


async def _get_package_from_request(request: web.Request) -> Package:
    server = request.app[QPyServer.APP_KEY]

    uri_package_hash: str | None = request.match_info.get("package_hash", None)
    parts = await _read_body_parts(request)

    if parts.package and uri_package_hash and uri_package_hash != parts.package.hash:
        msg = (
            f"The request URI specifies a package with hash '{uri_package_hash}', but the sent package has a hash of"
            f" '{parts.package.hash}'."
        )
        raise InvalidPackageError(reason=msg, temporary=False)

    package = None
    if uri_package_hash:
        package = server.package_collection.get(uri_package_hash)

    if not package and parts.package:
        try:
            package = await server.package_collection.put(parts.package)
        except CacheItemTooLargeError as e:
            raise web.HTTPRequestEntityTooLarge(max_size=e.max_size, actual_size=e.actual_size, text=str(e)) from e

    if not package:
        if uri_package_hash:
            msg = (
                f"The package was not provided, is not cached and could not be found by its hash. "
                f"('{uri_package_hash}')"
            )
            raise InvalidRequestError(reason=msg, temporary=False)
        msg = "The package is required but was not provided."
        raise InvalidRequestError(reason=msg, temporary=False)

    return package


def _get_main_body_param(handler: _HandlerFunc, signature: inspect.Signature) -> inspect.Parameter | None:
    candidates = [
        param
        for param in signature.parameters.values()
        if isinstance(param.annotation, type) and issubclass(param.annotation, MainBaseModel)
    ]

    if not candidates:
        # Handler doesn't use the main body.
        return None

    if len(candidates) > 1:
        msg = f"Handler function '{handler.__name__}' ambiguously takes multiple MainBaseModel parameters"
        raise TypeError(msg)

    return candidates[0]


def _get_package_param(handler: _HandlerFunc, signature: inspect.Signature) -> inspect.Parameter | None:
    candidates = [param for param in signature.parameters.values() if param.annotation is Package]

    if not candidates:
        # Handler doesn't use the package.
        return None

    if len(candidates) > 1:
        msg = f"Handler function '{handler.__name__}' ambiguously takes multiple Package parameters"
        raise TypeError(msg)

    return candidates[0]


class _RequestBodyParts(NamedTuple):
    main: bytes | None
    package: HashContainer | None
    question_state: bytes | None


_PARTS_REQUEST_KEY = "qpy-request-parts"


async def _read_body_parts(request: web.Request) -> _RequestBodyParts:
    # We can only read the body once, and we have to read all of it at once (since we make no assumption about the order
    # of the parts). Since we want to otherwise decouple main body, package, and question state handling logic, we cache
    # the read body as a request variable.
    parts: _RequestBodyParts = request.get(_PARTS_REQUEST_KEY, None)
    if parts:
        return parts

    if not request.body_exists:
        # No body sent at all.
        parts = _RequestBodyParts(None, None, None)
    elif request.content_type == "multipart/form-data":
        # Multiple parts.
        parts = await _parse_form_data(request)
    elif request.content_type == "application/json":
        # Just the main body part.
        parts = _RequestBodyParts(await request.read(), None, None)
    else:
        msg = (
            f"Wrong content type, expected multipart/form-data, application/json or no body, got "
            f"'{request.content_type}'"
        )
        web_logger.info(msg)
        raise web.HTTPUnsupportedMediaType(text=msg)

    request[_PARTS_REQUEST_KEY] = parts
    return parts


async def _parse_form_data(request: web.Request) -> _RequestBodyParts:
    """Parses a multipart/form-data request.

    Args:
        request (Request): The request to be parsed.

    Returns: tuple of main field, package, and question state
    """
    server = request.app[QPyServer.APP_KEY]
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

    return _RequestBodyParts(main, package, question_state)


_M = TypeVar("_M", bound=BaseModel)


def _validate_from_http(raw_body: str | bytes, param_class: type[_M]) -> _M:
    """Validates the given json which was presumably an HTTP body to the given Pydantic model.

    Args:
        raw_body: raw json body
        param_class: the [pydantic.BaseModel][] subclass to validate to
    """
    try:
        return param_class.model_validate_json(raw_body)
    except ValidationError as error:
        # TODO: Remove double logging? (Here and in the errors mixin.)
        web_logger.info("JSON does not match model: %s", error)
        raise InvalidRequestError(reason="Invalid JSON body", temporary=False) from error
