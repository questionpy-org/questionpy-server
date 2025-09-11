from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import NamedTuple

from aiohttp import web

from questionpy_common.environment import LmsProvidedAttributes, PackagePermissions, RequestInfo
from questionpy_common.manifest import Bcp47LanguageTag
from questionpy_server.models import LmsProvidedAttributes as LmsProvidedAttributesModel
from questionpy_server.models import RequestBaseData
from questionpy_server.package import Package
from questionpy_server.web import CURRENT_USER_KEY
from questionpy_server.web.app import QPyServer
from questionpy_server.worker import Worker


def get_request_info(
    _request: web.Request, *, lms_provided_attributes: LmsProvidedAttributes | None = None
) -> RequestInfo:
    """Retrieves the [RequestInfo][] object for the given request."""
    return RequestInfo(
        lms_provided_attributes=lms_provided_attributes,
        # TODO: Replace with Accept-Language header contents.
        preferred_languages=[Bcp47LanguageTag("de"), Bcp47LanguageTag("en")],
    )


class WorkerContext(NamedTuple):
    worker: Worker
    request_info: RequestInfo
    permissions: PackagePermissions


@asynccontextmanager
async def worker_context(request: web.Request, package: Package, data: RequestBaseData) -> AsyncIterator[WorkerContext]:
    """Returns the worker context for the given request."""
    qpyserver = request.app[QPyServer.APP_KEY]
    current_user = request.get(CURRENT_USER_KEY)
    permissions = qpyserver.package_permissions.get_effective_permissions(package, current_user, data.context)
    location = await package.get_zip_package_location()

    lms_provided_attributes = None
    if isinstance(data, LmsProvidedAttributesModel):
        lms_provided_attributes = data.lms_provided_attributes

    async with qpyserver.worker_pool.get_worker(location, current_user, data.context, permissions) as worker:
        yield WorkerContext(
            worker,
            get_request_info(request, lms_provided_attributes=lms_provided_attributes),
            permissions,
        )
