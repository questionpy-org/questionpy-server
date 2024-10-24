#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import Iterable

from aiohttp import web
from aiohttp.typedefs import Handler, Middleware
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

from questionpy_common.api.qtype import InvalidQuestionStateError
from questionpy_common.error import QPyBaseError
from questionpy_server.web.errors import (
    InvalidPackageError,
    OutOfMemoryError,
    PackageError,
    QPyWebBaseError,
    ServerError,
    WorkerTimeoutError,
)
from questionpy_server.worker.exception import (
    StaticFileSizeMismatchError,
    WorkerCPUTimeLimitExceededError,
    WorkerNotRunningError,
    WorkerRealTimeLimitExceededError,
    WorkerStartError,
)
from questionpy_server.worker.runtime.messages import WorkerMemoryLimitExceededError, WorkerUnknownError

exception_map: dict[type[QPyBaseError], type[QPyWebBaseError]] = {
    InvalidQuestionStateError: InvalidPackageError,
    StaticFileSizeMismatchError: InvalidPackageError,
    WorkerNotRunningError: InvalidPackageError,
    WorkerCPUTimeLimitExceededError: WorkerTimeoutError,
    WorkerRealTimeLimitExceededError: WorkerTimeoutError,
    WorkerStartError: ServerError,
    WorkerMemoryLimitExceededError: OutOfMemoryError,
    WorkerUnknownError: PackageError,
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
        exception = exception_map[e.__class__]
        raise exception(reason=e.reason, temporary=e.temporary) from e
    except Exception as e:
        raise ServerError(reason=e.__class__.__name__, temporary=True) from e


middlewares: Iterable[Middleware] = {error_middleware}
