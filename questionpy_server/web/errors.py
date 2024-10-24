#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import abstractmethod

from aiohttp import web
from aiohttp.log import web_logger

from questionpy_server.models import RequestError, RequestErrorCode


class QPyWebBaseError(Exception):
    @abstractmethod
    def __init__(self, *, reason: str | None = None, temporary: bool = False):
        pass


class _ExceptionMixin(web.HTTPException):
    def __init__(self, msg: str, body: RequestError | None = None) -> None:
        if body:
            # Send structured error body as JSON.
            super().__init__(reason=type(self).__name__, text=body.model_dump_json(), content_type="application/json")
            if body.reason:
                msg += f": {body.reason}"
        else:
            # Send the detailed message.
            super().__init__(reason=type(self).__name__, text=msg)

        # web.HTTPException uses the HTTP reason (which should be very short) as the exception message (which should be
        # detailed). This sets the message to our detailed one.
        Exception.__init__(self, msg)

        web_logger.info(msg)


class WorkerTimeoutError(web.HTTPBadRequest, _ExceptionMixin, QPyWebBaseError):
    def __init__(self, *, reason: str, temporary: bool) -> None:
        super().__init__(
            msg="Question package did not answer in a reasonable amount of time",
            body=RequestError(
                error_code=RequestErrorCode.OUT_OF_MEMORY,
                reason=reason,
                temporary=temporary,
            ),
        )


class OutOfMemoryError(web.HTTPBadRequest, _ExceptionMixin, QPyWebBaseError):
    def __init__(self, *, reason: str, temporary: bool) -> None:
        super().__init__(
            "Question package reached its memory limit",
            RequestError(
                error_code=RequestErrorCode.OUT_OF_MEMORY,
                reason=reason,
                temporary=temporary,
            ),
        )


class InvalidPackageError(web.HTTPBadRequest, _ExceptionMixin, QPyWebBaseError):
    def __init__(self, *, reason: str, temporary: bool) -> None:
        super().__init__(
            "Invalid package was provided",
            RequestError(
                error_code=RequestErrorCode.INVALID_PACKAGE,
                reason=reason,
                temporary=temporary,
            ),
        )


class InvalidRequestError(web.HTTPBadRequest, _ExceptionMixin, QPyWebBaseError):
    def __init__(self, *, reason: str, temporary: bool) -> None:
        super().__init__(
            "Invalid request body was provided",
            RequestError(
                error_code=RequestErrorCode.INVALID_REQUEST,
                reson=reason,
                temporary=temporary,
            ),
        )


class PackageError(web.HTTPBadRequest, _ExceptionMixin, QPyWebBaseError):
    def __init__(self, *, reason: str, temporary: bool) -> None:
        super().__init__(
            "An error occurred within the package",
            RequestError(
                error_code=RequestErrorCode.PACKAGE_ERROR,
                temporary=temporary,
                reason=reason,
            ),
        )


class ServerError(web.HTTPInternalServerError, _ExceptionMixin, QPyWebBaseError):
    def __init__(self, *, reason: str, temporary: bool) -> None:
        super().__init__(
            "There was an internal server error",
            RequestError(
                error_code=RequestErrorCode.SERVER_ERROR,
                temporary=temporary,
                reason=reason,
            ),
        )
