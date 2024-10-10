#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import json

import pytest
from aiohttp import web
from aiohttp.web_exceptions import HTTPException, HTTPBadRequest, HTTPNotFound, HTTPMethodNotAllowed
from aiohttp.pytest_plugin import AiohttpClient

from questionpy_common.error import TemporaryException
from questionpy_server.models import RequestError
from questionpy_server.web._errors import ServerError, InvalidPackageError, InvalidRequestError, OutOfMemoryError, WorkerTimeoutError, PackageError
from questionpy_server.web._middlewares import error_middleware
from questionpy_server.worker.exception import WorkerStartError, WorkerNotRunningError, WorkerCPUTimeLimitExceededError, StaticFileSizeMismatchError


def error_server(error: Exception) -> web.Application:
    async def raise_error(_):
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
    ]
)
async def test_http_exception_should_be_returned_as_is(aiohttp_client: AiohttpClient, error: HTTPException) -> None:
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response.status == error.status_code
    assert response.reason == error.reason


@pytest.mark.parametrize(
    "error",
    [
        ServerError(reason="a reason"),
        InvalidPackageError(reason="a reason"),
        InvalidRequestError(reason="a reason"),
        OutOfMemoryError(temporary=True),
        WorkerTimeoutError(temporary=False),
        PackageError(reason="a reason", temporary=True),
    ]
)
async def test_request_error_should_be_returned_as_is(aiohttp_client: AiohttpClient, error: HTTPException) -> None:
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response.status == error.status_code
    data = await response.json()
    assert RequestError(**json.loads(error.text)) == RequestError(**data)


@pytest.mark.parametrize(
    "error",
    [
        (WorkerNotRunningError(""), InvalidRequestError(reason="a reason")),
        (WorkerStartError(), 'test'),
        (WorkerCPUTimeLimitExceededError(), 'test'),
        (StaticFileSizeMismatchError(), 'test'),
    ]
)
async def test_worker_error_should_be_transformed_to_web_error(aiohttp_client: AiohttpClient, error: TemporaryException) -> None:
    server = error_server(WorkerStartError())
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response


@pytest.mark.parametrize(
    "error",
    [
        WorkerNotRunningError(),
        WorkerStartError(),
        WorkerCPUTimeLimitExceededError(),
        StaticFileSizeMismatchError(),
    ]
)
async def test_internal_worker_error_should_be_transformed_to_web_error(aiohttp_client: AiohttpClient, error: TemporaryException) -> None:
    server = error_server(WorkerStartError())
    client = await aiohttp_client(server)
    response = await client.get("")

    assert False


@pytest.mark.parametrize(
    "error",
    [
        Exception(),
        Exception("Oh no!")
    ],
)
async def test_unexpected_exception_should_return_server_error(aiohttp_client: AiohttpClient, error: Exception) -> None:
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get('')

    assert response.status == 500
    data = await response.json()
    assert data.items() >= {"error_code": "SERVER_ERROR", "temporary": False}.items()
    assert error.__class__.__name__ in data["reason"]

    msg = str(error).strip()
    if msg:
        assert msg in data["reason"]

