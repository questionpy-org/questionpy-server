#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from typing import Any

from aiohttp import web
from aiohttp.log import web_logger

from questionpy_common.api.qtype import MigrationErrorKind
from questionpy_server.models import MigrationError as MigrationErrorModel
from questionpy_server.models import OptionsFormValidationError, RequestError, RequestErrorCode


class _ExceptionMixin(web.HTTPException):
    def __init__(self, msg: str, body: RequestError) -> None:
        # Send structured error body as JSON.
        super().__init__(reason=type(self).__name__, text=body.model_dump_json(), content_type="application/json")
        if body.reason:
            msg += f": {body.reason}"

        # web.HTTPException uses the HTTP reason (which should be very short) as the exception message (which should be
        # detailed). This sets the message to our detailed one.
        Exception.__init__(self, msg)

        web_logger.info(msg)


class PackageEnvironmentVariablesError(web.HTTPForbidden, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        super().__init__(
            msg="Question package requires environment variables that are not provided by the server",
            body=RequestError(
                error_code=RequestErrorCode.PACKAGE_ENVIRONMENT_VARIABLES_ERROR,
                reason=reason,
                temporary=temporary,
            ),
        )


class PackagePermissionError(web.HTTPForbidden, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        super().__init__(
            msg="Question package requested more permissions than allowed",
            body=RequestError(
                error_code=RequestErrorCode.PACKAGE_PERMISSION_ERROR,
                reason=reason,
                temporary=temporary,
            ),
        )


class WorkerTimeoutError(web.HTTPInternalServerError, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        super().__init__(
            msg="Question package did not answer in a reasonable amount of time",
            body=RequestError(
                error_code=RequestErrorCode.WORKER_TIMEOUT,
                reason=reason,
                temporary=temporary,
            ),
        )


class OutOfMemoryError(web.HTTPInternalServerError, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        super().__init__(
            "Question package reached its memory limit",
            RequestError(
                error_code=RequestErrorCode.OUT_OF_MEMORY,
                reason=reason,
                temporary=temporary,
            ),
        )


class InvalidAttemptStateError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self, *, reason: str | None, **_: Any) -> None:
        super().__init__(
            "Invalid attempt state was provided",
            RequestError(
                error_code=RequestErrorCode.INVALID_ATTEMPT_STATE,
                reason=reason,
                temporary=False,
            ),
        )


class InvalidQuestionStateError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self, *, reason: str | None, **_: Any) -> None:
        super().__init__(
            "Invalid question state was provided",
            RequestError(
                error_code=RequestErrorCode.INVALID_QUESTION_STATE,
                reason=reason,
                temporary=False,
            ),
        )


class InvalidPackageError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self, *, reason: str | None, **_: Any) -> None:
        super().__init__(
            "Invalid package was provided",
            RequestError(
                error_code=RequestErrorCode.INVALID_PACKAGE,
                reason=reason,
                temporary=False,
            ),
        )


class InvalidRequestError(web.HTTPUnprocessableEntity, _ExceptionMixin):
    def __init__(self, *, reason: str | None, **_: Any) -> None:
        super().__init__(
            "Invalid request body was provided",
            RequestError(
                error_code=RequestErrorCode.INVALID_REQUEST,
                reason=reason,
                temporary=False,
            ),
        )


class InvalidOptionsFormError(web.HTTPUnprocessableEntity, _ExceptionMixin):
    def __init__(self, *, reason: str | None, errors: dict[str, str]) -> None:
        super().__init__(
            "Invalid form data was provided",
            OptionsFormValidationError(
                error_code=RequestErrorCode.INVALID_OPTIONS_FORM,
                reason=reason,
                temporary=False,
                errors=errors,
            ),
        )


class PackageError(web.HTTPInternalServerError, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        super().__init__(
            "An error occurred within the package",
            RequestError(
                error_code=RequestErrorCode.PACKAGE_ERROR,
                temporary=temporary,
                reason=reason,
            ),
        )


class PackageNotFoundError(web.HTTPNotFound, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        super().__init__(
            "Package was not found",
            RequestError(
                error_code=RequestErrorCode.PACKAGE_NOT_FOUND,
                temporary=temporary,
                reason=reason,
            ),
        )


class MigrationError(web.HTTPUnprocessableEntity, _ExceptionMixin):
    def __init__(self, *, reason: str | None, temporary: bool, kind: MigrationErrorKind) -> None:
        super().__init__(
            "Migration failed or is not possible.",
            MigrationErrorModel(
                error_code=RequestErrorCode.MIGRATION_ERROR,
                temporary=temporary,
                reason=reason,
                kind=kind,
            ),
        )


class ServerError(web.HTTPInternalServerError):
    def __init__(self, *, reason: str | None, temporary: bool) -> None:
        body = RequestError(
            error_code=RequestErrorCode.SERVER_ERROR,
            temporary=temporary,
            reason=reason,
        )
        super().__init__(reason=type(self).__name__, text=body.model_dump_json(), content_type="application/json")


QpyWebError = (
    PackagePermissionError
    | PackageEnvironmentVariablesError
    | WorkerTimeoutError
    | OutOfMemoryError
    | InvalidAttemptStateError
    | InvalidQuestionStateError
    | InvalidPackageError
    | InvalidRequestError
    | PackageError
    | PackageNotFoundError
    | ServerError
)
