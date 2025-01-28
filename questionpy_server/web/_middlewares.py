#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import Iterable

from aiohttp import web
from aiohttp.log import web_logger
from aiohttp.typedefs import Handler, Middleware
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

import questionpy_server.web.errors as web_error
from questionpy_common.api.qtype import InvalidAttemptStateError, InvalidQuestionStateError, OptionsFormValidationError
from questionpy_common.error import QPyBaseError
from questionpy_server.worker.exception import (
    StaticFileSizeMismatchError,
    WorkerCPUTimeLimitExceededError,
    WorkerRealTimeLimitExceededError,
    WorkerStartError,
)
from questionpy_server.worker.runtime.messages import WorkerMemoryLimitExceededError, WorkerUnknownError

exception_map: dict[type[QPyBaseError], type[web_error.QpyWebError]] = {
    InvalidAttemptStateError: web_error.InvalidAttemptStateError,
    InvalidQuestionStateError: web_error.InvalidQuestionStateError,
    StaticFileSizeMismatchError: web_error.InvalidPackageError,
    WorkerCPUTimeLimitExceededError: web_error.WorkerTimeoutError,
    WorkerRealTimeLimitExceededError: web_error.WorkerTimeoutError,
    WorkerStartError: web_error.ServerError,
    WorkerMemoryLimitExceededError: web_error.OutOfMemoryError,
    WorkerUnknownError: web_error.PackageError,
}


@web.middleware
async def error_middleware(request: Request, handler: Handler) -> StreamResponse:
    """Handles server and worker errors.

    Args:
        request: The incoming request.
        handler: The request handler.

    Returns:
        The response.
    """
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except tuple(exception_map.keys()) as e:
        exception = exception_map[type(e)]
        raise exception(reason=e.reason, temporary=e.temporary) from e
    except OptionsFormValidationError as e:
        raise web_error.InvalidOptionsFormError(reason=e.reason, errors=e.errors) from e
    except Exception as e:
        web_logger.exception("There was an unexpected error while processing the request.")
        raise web_error.ServerError(reason="unknown", temporary=True) from e


middlewares: Iterable[Middleware] = {error_middleware}
