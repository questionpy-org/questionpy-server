#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import TYPE_CHECKING

from aiohttp import web
from aiohttp.web_exceptions import HTTPMethodNotAllowed, HTTPNotFound

from questionpy_common.environment import RequestUser
from questionpy_server.models import QuestionCreateArguments, QuestionEditFormResponse, RequestBaseData
from questionpy_server.package import Package
from questionpy_server.web._decorators import ensure_package, ensure_required_parts
from questionpy_server.web._utils import pydantic_json_response
from questionpy_server.web.app import QPyServer
from questionpy_server.worker.runtime.package_location import ZipPackageLocation

if TYPE_CHECKING:
    from questionpy_server.worker import Worker

package_routes = web.RouteTableDef()


@package_routes.get("/packages")
async def get_packages(request: web.Request) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package_versions_infos = qpyserver.package_collection.get_package_versions_infos()
    return pydantic_json_response(data=package_versions_infos)


@package_routes.get(r"/packages/{package_hash:\w+}")
async def get_package(request: web.Request) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package = qpyserver.package_collection.get(request.match_info["package_hash"])
    if not package:
        raise HTTPNotFound

    return pydantic_json_response(data=package.get_info())


@package_routes.post(r"/packages/{package_hash:\w+}/options")
@ensure_required_parts
async def post_options(
    request: web.Request, package: Package, data: RequestBaseData, question_state: bytes | None = None
) -> web.Response:
    """Get the options form definition that allow a question creator to customize a question."""
    qpyserver = request.app[QPyServer.APP_KEY]

    package_path = await package.get_path()
    worker: Worker
    async with qpyserver.worker_pool.get_worker(ZipPackageLocation(package_path), 0, data.context) as worker:
        definition, form_data = await worker.get_options_form(
            RequestUser(["de", "en"]), question_state.decode() if question_state else None
        )

    return pydantic_json_response(data=QuestionEditFormResponse(definition=definition, form_data=form_data))


@package_routes.post(r"/packages/{package_hash:\w+}/question")
@ensure_required_parts
async def post_question(
    request: web.Request, data: QuestionCreateArguments, package: Package, question_state: bytes | None = None
) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package_path = await package.get_path()
    worker: Worker
    async with qpyserver.worker_pool.get_worker(ZipPackageLocation(package_path), 0, data.context) as worker:
        question = await worker.create_question_from_options(
            RequestUser(["de", "en"]), question_state.decode() if question_state else None, data.form_data
        )

    return pydantic_json_response(data=question)


@package_routes.post(r"/packages/{package_hash:\w+}/question/migrate")
async def post_question_migrate(_request: web.Request) -> web.Response:
    msg = ""
    raise HTTPMethodNotAllowed(msg, "")


@package_routes.post(r"/package-extract-info")
@ensure_package
async def package_extract_info(_request: web.Request, package: Package) -> web.Response:
    """Get package information."""
    return pydantic_json_response(data=package.get_info(), status=201)
