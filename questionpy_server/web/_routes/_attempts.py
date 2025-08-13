#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from aiohttp import web

from questionpy_server.models import (
    AttemptResponse,
    AttemptScoreArguments,
    AttemptScoredResponse,
    AttemptStartArguments,
    AttemptStartedResponse,
    AttemptViewArguments,
)
from questionpy_server.package import Package
from questionpy_server.web._decorators import ensure_required_parts
from questionpy_server.web._utils import CURRENT_USER_KEY, DEFAULT_REQUEST_USER, pydantic_json_response
from questionpy_server.web.app import QPyServer

attempt_routes = web.RouteTableDef()


@attempt_routes.post(r"/packages/{package_hash:\w+}/attempt/start")
@ensure_required_parts
async def post_attempt_start(
    request: web.Request, package: Package, question_state: bytes, data: AttemptStartArguments
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    current_user = request.get(CURRENT_USER_KEY)
    permissions = qpyserver.worker_permissions.get_effective_permissions(package, current_user, data.context)
    location = await package.get_zip_package_location()

    async with qpyserver.worker_pool.get_worker(location, current_user, data.context, permissions) as worker:
        attempt = await worker.start_attempt(DEFAULT_REQUEST_USER, question_state.decode(), data.variant)
        packages = worker.get_loaded_packages()

    resp = AttemptStartedResponse(**dict(attempt), package_dependencies=packages)
    return pydantic_json_response(data=resp, status=201)


@attempt_routes.post(r"/packages/{package_hash:\w+}/attempt/view")
@ensure_required_parts
async def post_attempt_view(
    request: web.Request, package: Package, question_state: bytes, data: AttemptViewArguments
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    current_user = request.get(CURRENT_USER_KEY)
    permissions = qpyserver.worker_permissions.get_effective_permissions(package, current_user, data.context)
    location = await package.get_zip_package_location()

    async with qpyserver.worker_pool.get_worker(location, current_user, data.context, permissions) as worker:
        attempt = await worker.get_attempt(
            request_user=DEFAULT_REQUEST_USER,
            question_state=question_state.decode(),
            attempt_state=data.attempt_state,
            scoring_state=data.scoring_state,
            response=data.response,
        )
        packages = worker.get_loaded_packages()

    resp = AttemptResponse(**dict(attempt), package_dependencies=packages)
    return pydantic_json_response(data=resp, status=201)


@attempt_routes.post(r"/packages/{package_hash:\w+}/attempt/score")
@ensure_required_parts
async def post_attempt_score(
    request: web.Request, package: Package, question_state: bytes, data: AttemptScoreArguments
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    current_user = request.get(CURRENT_USER_KEY)
    permissions = qpyserver.worker_permissions.get_effective_permissions(package, current_user, data.context)
    location = await package.get_zip_package_location()

    async with qpyserver.worker_pool.get_worker(location, current_user, data.context, permissions) as worker:
        attempt_scored = await worker.score_attempt(
            request_user=DEFAULT_REQUEST_USER,
            question_state=question_state.decode(),
            attempt_state=data.attempt_state,
            scoring_state=data.scoring_state,
            response=data.response,
        )
        packages = worker.get_loaded_packages()

    resp = AttemptScoredResponse(**dict(attempt_scored), package_dependencies=packages)
    return pydantic_json_response(data=resp, status=201)
