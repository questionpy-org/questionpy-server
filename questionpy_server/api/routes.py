#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import TYPE_CHECKING, Optional

from aiohttp import web
from aiohttp.web_exceptions import HTTPMethodNotAllowed, HTTPNotFound

from questionpy_server.factories import AttemptFactory, AttemptScoredFactory, AttemptStartedFactory
from questionpy_server.web import ensure_package_and_question_state_exist, json_response
from .models import AttemptStartArguments, AttemptScoreArguments, AttemptViewArguments, \
    QuestionCreateArguments, QuestionEditFormResponse, RequestBaseData
from ..package import Package

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer

routes = web.RouteTableDef()


@routes.get('/packages')
async def get_packages(request: web.Request) -> web.Response:
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    packages = qpyserver.package_collection.get_packages()
    data = [package.get_info() for package in packages]

    return json_response(data=data)


@routes.get(r'/packages/{package_hash:\w+}')
async def get_package(request: web.Request) -> web.Response:
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    try:
        package = qpyserver.package_collection.get(request.match_info['package_hash'])
        return json_response(data=package.get_info())
    except FileNotFoundError as error:
        raise HTTPNotFound from error


@routes.post(r'/packages/{package_hash:\w+}/options')  # type: ignore[arg-type]
@ensure_package_and_question_state_exist
# pylint: disable=unused-argument
async def post_options(request: web.Request, package: Package, question_state: Optional[bytes],
                       data: RequestBaseData) -> web.Response:
    """Get the options form definition that allow a question creator to customize a question."""
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    package_path = await package.get_path()
    async with qpyserver.worker_pool.get_worker(package_path, 0, data.context) as worker:
        definition, form_data = await worker.get_options_form(question_state)

    return json_response(data=QuestionEditFormResponse(definition=definition, form_data=form_data))


@routes.post(r'/packages/{package_hash:\w+}/attempt/start')  # type: ignore[arg-type]
@ensure_package_and_question_state_exist
# pylint: disable=unused-argument
async def post_attempt_start(_request: web.Request, package: Package, question_state: bytes,
                             data: AttemptStartArguments) -> web.Response:
    return json_response(data=AttemptStartedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/view')  # type: ignore[arg-type]
@ensure_package_and_question_state_exist
# pylint: disable=unused-argument
async def post_attempt_view(_request: web.Request, package: Package, question_state: bytes,
                            data: AttemptViewArguments) -> web.Response:
    return json_response(data=AttemptFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/score')  # type: ignore[arg-type]
@ensure_package_and_question_state_exist
# pylint: disable=unused-argument
async def post_attempt_score(_request: web.Request, package: Package, question_state: bytes,
                             data: AttemptScoreArguments) -> web.Response:
    return json_response(data=AttemptScoredFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/question')  # type: ignore[arg-type]
@ensure_package_and_question_state_exist
async def post_question(request: web.Request, data: QuestionCreateArguments,
                        package: Package, question_state: Optional[bytes] = None) -> web.Response:
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    package_path = await package.get_path()
    async with qpyserver.worker_pool.get_worker(package_path, 0, data.context) as worker:
        question = await worker.create_question_from_options(question_state, data.form_data)

    return json_response(data=question)


@routes.post(r'/packages/{package_hash:\w+}/question/migrate')
async def post_question_migrate(_request: web.Request) -> web.Response:
    raise HTTPMethodNotAllowed("", "")


@routes.post(r'/package-extract-info')  # type: ignore[arg-type]
@ensure_package_and_question_state_exist
async def package_extract_info(_request: web.Request, package: Package) -> web.Response:
    """Get package information."""
    return json_response(data=package.get_info(), status=201)
