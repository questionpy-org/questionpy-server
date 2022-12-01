from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aiohttp import web
from aiohttp.web_exceptions import HTTPMethodNotAllowed, HTTPNotFound

from questionpy_server.web import ensure_package_and_question_state_exists, json_response, ensure_package_exists
from questionpy_server.factories import AttemptFactory, AttemptGradedFactory, AttemptStartedFactory

from .models import QuestionStateHash, AttemptStartArguments, AttemptGradeArguments, AttemptViewArguments
from ..package import Package

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer

routes = web.RouteTableDef()


@routes.post(r'/packages/{package_hash:\w+}')  # type: ignore[arg-type]
@ensure_package_exists
async def post_package(_request: web.Request, package: Package) -> web.Response:
    """Get package information."""
    return json_response(data=package.get_info())


@routes.get('/packages')
async def get_packages(request: web.Request) -> web.Response:
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    packages = await qpyserver.collector.get_packages()
    data = [package.get_info() for package in packages]

    return json_response(data=data)


@routes.get(r'/packages/{package_hash:\w+}')
async def get_package(request: web.Request) -> web.Response:
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    try:
        package = await qpyserver.collector.get(request.match_info['package_hash'])
        return json_response(data=package.get_info())
    except FileNotFoundError:
        raise HTTPNotFound


@routes.post(r'/packages/{package_hash:\w+}/options')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists(optional_question_state=True)
async def post_options(request: web.Request, package: Package, question_state: Optional[Path],
                       data: QuestionStateHash) -> web.Response:
    """
    Get the options form definition that allow a question creator to customize a question.
    """
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    package_path = await package.get_path()
    async with qpyserver.worker_pool.get_worker(package_path, 0, data.context) as worker:
        options = await worker.get_options_form_definition()
    return json_response(data=options)


@routes.post(r'/packages/{package_hash:\w+}/attempt/start')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_attempt_start(_request: web.Request, package: Package, question_state: Path,
                             _data: AttemptStartArguments) -> web.Response:
    return json_response(data=AttemptStartedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/view')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_attempt_view(_request: web.Request, package: Package, question_state: Path,
                            _data: AttemptViewArguments) -> web.Response:
    return json_response(data=AttemptFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/grade')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_attempt_grade(_request: web.Request, package: Package, question_state: Path,
                             _data: AttemptGradeArguments) -> web.Response:
    return json_response(data=AttemptGradedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/question')
async def post_question(_request: web.Request) -> web.Response:
    raise HTTPMethodNotAllowed("", "")


@routes.post(r'/packages/{package_hash:\w+}/question/migrate')
async def post_question_migrate(_request: web.Request) -> web.Response:
    raise HTTPMethodNotAllowed("", "")
