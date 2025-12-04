#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from aiohttp import web

from questionpy_common.api.question import LmsPermissions
from questionpy_server.models import (
    QuestionCreateArguments,
    QuestionEditFormResponse,
    QuestionSidegradeArguments,
    QuestionUpgradeArguments,
    RequestBaseData,
)
from questionpy_server.package import Package
from questionpy_server.web._decorators import ensure_package, ensure_required_parts
from questionpy_server.web._utils import pydantic_json_response
from questionpy_server.web._worker_context import worker_context
from questionpy_server.web.app import QPyServer
from questionpy_server.web.errors import PackageNotFoundError

package_routes = web.RouteTableDef()


@package_routes.get("/packages")
async def get_packages(request: web.Request) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]
    package_versions_infos = qpyserver.package_collection.get_package_versions_infos()
    return pydantic_json_response(data=package_versions_infos)


@package_routes.get(r"/packages/{package_hash:\w+}")
async def get_package(request: web.Request) -> web.Response:
    qpyserver = request.app[QPyServer.APP_KEY]

    package_hash = request.match_info["package_hash"]
    package = qpyserver.package_collection.get(package_hash)
    if not package:
        msg = f"A package with the given hash was not found. ('{package_hash}')"
        raise PackageNotFoundError(reason=msg, temporary=False)

    return pydantic_json_response(data=package.get_info())


@package_routes.post(r"/packages/{package_hash:\w+}/options")
@ensure_required_parts
async def post_options(
    request: web.Request, package: Package, data: RequestBaseData, question_state: bytes | None = None
) -> web.Response:
    """Get the options form definition that allow a question creator to customize a question."""
    async with worker_context(request, package, data) as context:
        definition, form_data = await context.worker.get_options_form(
            context.request_info, question_state.decode() if question_state else None
        )
        packages = context.worker.get_loaded_packages()

    return pydantic_json_response(
        data=QuestionEditFormResponse(definition=definition, form_data=form_data, package_dependencies=packages)
    )


@package_routes.post(r"/packages/{package_hash:\w+}/question")
@ensure_required_parts
async def post_question(
    request: web.Request, package: Package, data: QuestionCreateArguments, question_state: bytes | None = None
) -> web.Response:
    async with worker_context(request, package, data) as context:
        lms_permissions = None
        if context.permissions.lms_attributes:
            lms_permissions = LmsPermissions(attributes=context.permissions.lms_attributes)

        question = await context.worker.create_question_from_options(
            context.request_info,
            question_state.decode() if question_state else None,
            data.form_data,
            lms_permissions,
        )

    return pydantic_json_response(data=question)


@package_routes.post(r"/packages/{package_hash:\w+}/question/upgrade")
@ensure_required_parts
async def post_question_upgrade(request: web.Request, package: Package, data: QuestionUpgradeArguments) -> web.Response:
    async with worker_context(request, package, data) as context:
        new_question_state = await context.worker.upgrade_question(
            context.request_info,
            data.question_state,
        )

    return pydantic_json_response(data=new_question_state)


@package_routes.post(r"/packages/{package_hash:\w+}/question/sidegrade")
@ensure_required_parts
async def post_question_sidegrade(
    request: web.Request, package: Package, data: QuestionSidegradeArguments
) -> web.Response:
    async with worker_context(request, package, data) as context:
        new_question_state = await context.worker.sidegrade_question(
            context.request_info,
            data.question_state,
        )

    return pydantic_json_response(data=new_question_state)


@package_routes.post(r"/package-extract-info")
@ensure_package
async def package_extract_info(_request: web.Request, package: Package) -> web.Response:
    """Get package information."""
    return pydantic_json_response(data=package.get_info(), status=201)
