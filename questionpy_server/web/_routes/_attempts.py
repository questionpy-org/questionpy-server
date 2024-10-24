#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import TYPE_CHECKING

from aiohttp import web

from questionpy_common.environment import RequestUser
from questionpy_server.models import AttemptScoreArguments, AttemptStartArguments, AttemptViewArguments
from questionpy_server.package import Package
from questionpy_server.web._decorators import ensure_required_parts
from questionpy_server.web._utils import pydantic_json_response
from questionpy_server.web.app import QPyServer
from questionpy_server.worker.runtime.package_location import ZipPackageLocation

if TYPE_CHECKING:
    from questionpy_server.worker import Worker

attempt_routes = web.RouteTableDef()


@attempt_routes.post(r"/packages/{package_hash:\w+}/attempt/start")
@ensure_required_parts
async def post_attempt_start(
    request: web.Request, package: Package, question_state: bytes, data: AttemptStartArguments
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package_path = await package.get_path()
    worker: Worker
    async with qpyserver.worker_pool.get_worker(ZipPackageLocation(package_path), 0, data.context) as worker:
        attempt = await worker.start_attempt(RequestUser(["de", "en"]), question_state.decode(), data.variant)

    return pydantic_json_response(data=attempt, status=201)


@attempt_routes.post(r"/packages/{package_hash:\w+}/attempt/view")
@ensure_required_parts
async def post_attempt_view(
    request: web.Request, package: Package, question_state: bytes, data: AttemptViewArguments
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package_path = await package.get_path()
    worker: Worker
    async with qpyserver.worker_pool.get_worker(ZipPackageLocation(package_path), 0, data.context) as worker:
        attempt = await worker.get_attempt(
            request_user=RequestUser(["de", "en"]),
            question_state=question_state.decode(),
            attempt_state=data.attempt_state,
            scoring_state=data.scoring_state,
            response=data.response,
        )

    return pydantic_json_response(data=attempt, status=201)


@attempt_routes.post(r"/packages/{package_hash:\w+}/attempt/score")
@ensure_required_parts
async def post_attempt_score(
    request: web.Request, package: Package, question_state: bytes, data: AttemptScoreArguments
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package_path = await package.get_path()
    worker: Worker
    async with qpyserver.worker_pool.get_worker(ZipPackageLocation(package_path), 0, data.context) as worker:
        attempt_scored = await worker.score_attempt(
            request_user=RequestUser(["de", "en"]),
            question_state=question_state.decode(),
            attempt_state=data.attempt_state,
            scoring_state=data.scoring_state,
            response=data.response,
        )

    return pydantic_json_response(data=attempt_scored, status=201)
