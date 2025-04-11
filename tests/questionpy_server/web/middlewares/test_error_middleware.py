#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import logging
from typing import Any, NoReturn

import pytest
from aiohttp import MultipartWriter, web
from aiohttp.pytest_plugin import AiohttpClient
from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPBadRequest, HTTPException, HTTPMethodNotAllowed, HTTPNotFound

from questionpy_common.api.qtype import InvalidQuestionStateError
from questionpy_common.error import QPyBaseError
from questionpy_server.models import RequestError, RequestErrorCode
from questionpy_server.web.errors import (
    InvalidPackageError,
    InvalidRequestError,
    OutOfMemoryError,
    PackageError,
    QpyWebError,
    ServerError,
    WorkerTimeoutError,
)
from questionpy_server.web.middlewares._error import error_middleware
from questionpy_server.worker.exception import (
    StaticFileSizeMismatchError,
    WorkerCPUTimeLimitExceededError,
    WorkerNotRunningError,
    WorkerRealTimeLimitExceededError,
    WorkerStartError,
)
from questionpy_server.worker.runtime.messages import (
    BaseWorkerError,
    WorkerMemoryLimitExceededError,
    WorkerUnknownError,
)
from tests.conftest import PACKAGE


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
    aiohttp_client: AiohttpClient, error_type: type[QpyWebError]
) -> None:
    error = error_type(reason="reason", temporary=False)
    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    assert response.status == error.status_code
    data = await response.json()
    RequestError(**data)


@pytest.mark.parametrize(
    "error_type",
    [
        WorkerNotRunningError,
        WorkerStartError,
        WorkerMemoryLimitExceededError,
        InvalidQuestionStateError,
        WorkerUnknownError,
        StaticFileSizeMismatchError,
    ],
)
async def test_qpy_base_error_should_be_transformed_to_web_error(
    aiohttp_client: AiohttpClient, error_type: type[QPyBaseError]
) -> None:
    error: QPyBaseError
    if issubclass(error_type, BaseWorkerError):
        error = error_type(reason="reason", temporary=False, worker_name="aae11272c5-0-N-nrrgqz3tm")
    else:
        error = error_type(reason="reason", temporary=False)

    server = error_server(error)
    client = await aiohttp_client(server)
    response = await client.get("")

    data = await response.json()
    RequestError(**data)


@pytest.mark.parametrize(
    "error_type",
    [
        WorkerCPUTimeLimitExceededError,
        WorkerRealTimeLimitExceededError,
    ],
)
async def test_time_limit_exception_should_be_transformed_to_web_error(
    aiohttp_client: AiohttpClient, error_type: type[WorkerCPUTimeLimitExceededError | WorkerRealTimeLimitExceededError]
) -> None:
    error = error_type(3, worker_name="aae11272c5-2-1-n5stk6tu")
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
async def test_unexpected_exception_should_return_server_error(
    aiohttp_client: AiohttpClient, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    server = error_server(error)
    client = await aiohttp_client(server)

    with caplog.at_level(logging.ERROR):
        response = await client.get("")

    assert response.status == 500
    data = await response.json()
    assert (
        data.items()
        == {
            "error_code": RequestErrorCode.SERVER_ERROR.value,
            "temporary": True,
            "reason": "unknown",
        }.items()
    )

    assert len(caplog.record_tuples) == 1
    [(logger_name, log_level, message)] = caplog.record_tuples
    assert logger_name == "aiohttp.web"
    assert "unexpected error" in message
    assert log_level == logging.ERROR


async def test_invalid_options_form_data_error(client: TestClient) -> None:
    with PACKAGE.path.open("rb") as package_fd, MultipartWriter("form-data") as writer:
        part = writer.append(package_fd)
        part.set_content_disposition("form-data", name="package")

        part = writer.append_json({"form_data": {}})
        part.set_content_disposition("form-data", name="main")

        res = await client.post(
            f"/packages/{PACKAGE.hash}/question",
            data=writer,
        )

    assert res.status == 422
    data = await res.json()
    assert (
        data.items()
        >= {
            "error_code": RequestErrorCode.INVALID_OPTIONS_FORM.value,
            "temporary": False,
            "reason": None,
        }.items()
    )

    assert data["errors"].items() == {"my_hidden": "Field required", "my_repetition": "Field required"}.items()
