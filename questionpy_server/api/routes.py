from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aiohttp import web
from aiohttp.web_exceptions import HTTPMethodNotAllowed, HTTPNotFound

from questionpy_server.factories import AttemptFactory, AttemptGradedFactory, AttemptStartedFactory
from questionpy_server.web import ensure_package_and_question_state_exists, json_response, ensure_package_exists
from .models import AttemptStartArguments, AttemptGradeArguments, AttemptViewArguments, \
    QuestionCreateArguments, Question, GradingMethod, OptionalQuestionStateHash
from ..package import Package
from ..worker.runtime.messages import GetOptionsFormDefinition, CreateQuestionFromOptions

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
@ensure_package_and_question_state_exists
# pylint: disable=unused-argument
async def post_options(request: web.Request, package: Package, question_state: Optional[Path],
                       data: OptionalQuestionStateHash) -> web.Response:
    """
    Get the options form definition that allow a question creator to customize a question.
    """
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    package_path = await package.get_path()
    async with qpyserver.worker_pool.get_worker(package_path, 0, data.context) as worker:
        response = await worker.send_and_wait_response(GetOptionsFormDefinition(), GetOptionsFormDefinition.Response)
    return json_response(data=response.definition)


@routes.post(r'/packages/{package_hash:\w+}/attempt/start')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
# pylint: disable=unused-argument
async def post_attempt_start(_request: web.Request, package: Package, question_state: Path,
                             _data: AttemptStartArguments) -> web.Response:
    return json_response(data=AttemptStartedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/view')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
# pylint: disable=unused-argument
async def post_attempt_view(_request: web.Request, package: Package, question_state: Path,
                            _data: AttemptViewArguments) -> web.Response:
    return json_response(data=AttemptFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/grade')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
# pylint: disable=unused-argument
async def post_attempt_grade(_request: web.Request, package: Package, question_state: Path,
                             _data: AttemptGradeArguments) -> web.Response:
    return json_response(data=AttemptGradedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/question')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_question(request: web.Request, data: QuestionCreateArguments,
                        package: Package, question_state: Optional[Path] = None) -> web.Response:
    qpyserver: 'QPyServer' = request.app['qpy_server_app']

    # Read state
    state_data: Optional[bytes] = None
    if question_state:
        with question_state.open("rb") as state_file:
            state_data = state_file.read()

    package_path = await package.get_path()
    async with qpyserver.worker_pool.get_worker(package_path, 0, data.context) as worker:
        response = await worker.send_and_wait_response(
            CreateQuestionFromOptions(state=state_data, form_data=data.form_data),
            CreateQuestionFromOptions.Response
        )

    new_state_hash = sha256(response.state.encode()).hexdigest()

    return json_response(data=Question(
        question_state=response.state,
        question_state_hash=new_state_hash,
        grading_method=GradingMethod.ALWAYS_MANUAL_GRADING_REQUIRED,
        response_analysis_by_variant=False
    ))


@routes.post(r'/packages/{package_hash:\w+}/question/migrate')
async def post_question_migrate(_request: web.Request) -> web.Response:
    raise HTTPMethodNotAllowed("", "")


@routes.post(r'/package-extract-info')  # type: ignore[arg-type]
@ensure_package_exists(required_hash=False)
async def package_extract_info(_request: web.Request, package: Package) -> web.Response:
    """Get package information."""
    return json_response(data=package.get_info(), status=201)
