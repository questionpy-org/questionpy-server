#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import Iterable

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.typedefs import Handler, Middleware

from questionpy_common.error import TemporaryException
from questionpy_server.package import Package
from questionpy_server.web._errors import ServerError, InvalidPackageError, WorkerTimeoutError, PackageError, OutOfMemoryError
from questionpy_server.worker.exception import (WorkerCPUTimeLimitExceededError, WorkerStartError,
                                                WorkerNotRunningError, StaticFileSizeMismatchError)
from questionpy_server.worker.runtime.messages import WorkerUnknownError, WorkerMemoryLimitExceededError


@web.middleware
async def error_middleware(request: Request, handler: Handler):
    """
    Handles server and worker errors.

    Args:
        request:
        handler:

    Returns:

    """
    def format_exception_msg(exception: Exception) -> str:
        exception_str = str(exception)
        message = exception.__class__.__name__
        message += ": " + exception_str if exception_str.strip() else ""
        return message

    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except (WorkerNotRunningError, WorkerStartError, StaticFileSizeMismatchError) as e:
        msg = format_exception_msg(e)
        raise InvalidPackageError(reason=msg) from e
    except WorkerCPUTimeLimitExceededError as e:
        raise WorkerTimeoutError(temporary=e.temporary) from e
    except WorkerMemoryLimitExceededError as e:
        raise OutOfMemoryError(temporary=False) from e
    except WorkerUnknownError as e:
        msg = format_exception_msg(e)
        raise PackageError(reason=msg, temporary=False) from e
    except QpyException as e:
        pass
    except Exception as e:
        # TODO: Probably too sensitive.
        msg = format_exception_msg(e)
        raise ServerError(reason=msg) from e


middlewares: Iterable[Middleware] = [error_middleware]
