from hashlib import sha1
from pathlib import Path

from aiohttp import web
from aiohttp.web_exceptions import HTTPMethodNotAllowed

from questionpy_common.dev.factories import OptionsFormDefinitionFactory

from questionpy_server.web import ensure_package_and_question_state_exists, json_response
from questionpy_server.factories import AttemptFactory, AttemptGradedFactory, AttemptStartedFactory,\
    PackageInfoFactory

from .models import QuestionStateHash, AttemptStartArguments, AttemptGradeArguments, AttemptViewArguments


routes = web.RouteTableDef()


@routes.get('/helloworld')
async def hello(_request: web.Request) -> web.Response:
    return web.Response(text="Hello, world")


@routes.get('/packages')
async def get_packages(_request: web.Request) -> web.Response:
    package_list = PackageInfoFactory.batch(5)
    response = json_response(data=package_list)
    return response


@routes.get(r'/packages/{package_hash:\w+}')
async def get_package(request: web.Request) -> web.Response:
    seed = int(sha1(request.match_info['package_hash'].encode()).hexdigest(), 16)
    PackageInfoFactory.seed_random(seed)
    response = json_response(data=PackageInfoFactory.build())
    return response


@routes.post(r'/packages/{package_hash:\w+}/options')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_options(_request: web.Request, package: Path, question_state: Path,
                       _data: QuestionStateHash) -> web.Response:
    return json_response(data=OptionsFormDefinitionFactory.build())


@routes.post(r'/packages/{package_hash:\w+}/attempt/start')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_attempt_start(_request: web.Request, package: Path, question_state: Path,
                             _data: AttemptStartArguments) -> web.Response:
    return json_response(data=AttemptStartedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/view')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_attempt_view(_request: web.Request, package: Path, question_state: Path,
                            _data: AttemptViewArguments) -> web.Response:
    return json_response(data=AttemptFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/attempt/grade')  # type: ignore[arg-type]
@ensure_package_and_question_state_exists
async def post_attempt_grade(_request: web.Request, package: Path, question_state: Path,
                             _data: AttemptGradeArguments) -> web.Response:
    return json_response(data=AttemptGradedFactory.build(), status=201)


@routes.post(r'/packages/{package_hash:\w+}/question')
async def post_question(_request: web.Request) -> web.Response:
    raise HTTPMethodNotAllowed("", "")


@routes.post(r'/packages/{package_hash:\w+}/question/migrate')
async def post_question_migrate(_request: web.Request) -> web.Response:
    raise HTTPMethodNotAllowed("", "")
