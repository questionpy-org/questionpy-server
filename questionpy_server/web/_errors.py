#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from aiohttp import web
from aiohttp.log import web_logger
from pydantic import BaseModel

from questionpy_server.models import NotFoundStatus, NotFoundStatusWhat


class _ExceptionMixin(web.HTTPException):
    def __init__(self, msg: str, body: BaseModel | None = None) -> None:
        if body:
            # Send structured error body as JSON.
            super().__init__(reason=type(self).__name__, text=body.model_dump_json(), content_type="application/json")
        else:
            # Send the detailed message.
            super().__init__(reason=type(self).__name__, text=msg)

        # web.HTTPException uses the HTTP reason (which should be very short) as the exception message (which should be
        # detailed). This sets the message to our detailed one.
        Exception.__init__(self, msg)

        web_logger.info(msg)


class MainBodyMissingError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self) -> None:
        super().__init__("The main body is required but was not provided.")


class PackageMissingWithoutHashError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self) -> None:
        super().__init__("The package is required but was not provided.")


class PackageMissingByHashError(web.HTTPNotFound, _ExceptionMixin):
    def __init__(self, package_hash: str) -> None:
        super().__init__(
            f"The package was not provided, is not cached and could not be found by its hash. ('{package_hash}')",
            NotFoundStatus(what=NotFoundStatusWhat.PACKAGE),
        )


class PackageHashMismatchError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self, from_uri: str, from_body: str) -> None:
        super().__init__(
            f"The request URI specifies a package with hash '{from_uri}', but the sent package has a hash of "
            f"'{from_body}'."
        )


class QuestionStateMissingError(web.HTTPBadRequest, _ExceptionMixin):
    def __init__(self) -> None:
        super().__init__(
            "A question state part is required but was not provided.",
            NotFoundStatus(what=NotFoundStatusWhat.QUESTION_STATE),
        )
