#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import json
from typing import Any, NoReturn

import pytest
from aiohttp import web
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.web_exceptions import HTTPBadRequest, HTTPException, HTTPMethodNotAllowed, HTTPNotFound

from questionpy_common.api.qtype import InvalidQuestionStateError
from questionpy_common.error import QPyBaseError
from questionpy_server.models import RequestError, RequestErrorCode
from questionpy_server.web._middlewares import error_middleware
from questionpy_server.web.errors import (
    InvalidPackageError,
    InvalidRequestError,
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


def error_server(error: Exception) -> web.Application:
    async def raise_error(_: Any) -> NoReturn:
        raise error

    app = web.Application(middlewares=[error_middleware])
    app.router.add_get("/{_:.*}", raise_error)
    return app


@pytest.mark.parametrize(
    "error",
    [
        HTTPBadRequest(),
        HTTPNotFound(),
        HTTPMethodNotAllowed("POST", []),
    ],
)
async def test_http_exception_should_be_returned_as_is(aiohttp_client: AiohttpClient, error: HTTPException) -> None:
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response.status == error.status_code
    assert response.reason == error.reason


@pytest.mark.parametrize(
    "error_type",
    [
        ServerError,
        InvalidPackageError,
        InvalidRequestError,
        OutOfMemoryError,
        WorkerTimeoutError,
        PackageError,
    ],
)
async def test_request_error_should_be_returned_as_is(
    aiohttp_client: AiohttpClient, error_type: type[QPyWebBaseError]
) -> None:
    error = error_type(reason="reason", temporary=False)
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response.status == error.status_code
    data = await response.json()
    assert RequestError(**json.loads(error.body)) == RequestError(**data)


@pytest.mark.parametrize(
    "error_type",
    [
        WorkerNotRunningError,
        WorkerStartError,
        WorkerCPUTimeLimitExceededError,
        WorkerRealTimeLimitExceededError,
        WorkerMemoryLimitExceededError,
        InvalidQuestionStateError,
        WorkerUnknownError,
        StaticFileSizeMismatchError,
    ],
)
async def test_worker_error_should_be_transformed_to_web_error(
    aiohttp_client: AiohttpClient, error_type: type[QPyBaseError]
) -> None:
    error = error_type(reason="reason", temporary=False)
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    data = await response.json()
    RequestError(**data)


class MyVeryCustomError(Exception): ...


@pytest.mark.parametrize(
    "error",
    [Exception(), Exception("Oh no!"), MyVeryCustomError("Oh no!")],
)
async def test_unexpected_exception_should_return_server_error(aiohttp_client: AiohttpClient, error: Exception) -> None:
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response.status == 500
    data = await response.json()
    assert data.items() >= {"error_code": RequestErrorCode.SERVER_ERROR.value, "temporary": True}.items()
    assert error.__class__.__name__ == data["reason"]
