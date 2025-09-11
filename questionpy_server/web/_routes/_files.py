#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotImplemented

from questionpy_server.package import Package
from questionpy_server.web import CURRENT_USER_KEY
from questionpy_server.web._decorators import ensure_package
from questionpy_server.web.app import QPyServer

file_routes = web.RouteTableDef()


@file_routes.post(r"/packages/{package_hash}/file/{namespace}/{short_name}/{path:static/.*}")
@ensure_package
async def serve_static_file(request: web.Request, package: Package) -> web.Response:
    qpy_server = request.app[QPyServer.APP_KEY]
    namespace = request.match_info["namespace"]
    short_name = request.match_info["short_name"]
    path = request.match_info["path"]

    if package.manifest.namespace != namespace or package.manifest.short_name != short_name:
        # TODO: Support static files in non-main packages by using namespace and short_name.
        raise HTTPNotImplemented(text="Static file retrieval from non-main packages is not supported yet.")

    current_user = request.get(CURRENT_USER_KEY)
    permissions = qpy_server.package_permissions.get_effective_permissions(package, current_user, "files")
    location = await package.get_zip_package_location()

    async with qpy_server.worker_pool.get_worker(location, current_user, "files", permissions) as worker:
        try:
            file = await worker.get_static_file(path)
        except FileNotFoundError as e:
            raise web.HTTPNotFound(text="File not found.") from e

    return web.Response(
        body=file.data,
        content_type=file.mime_type,
        # Set a lifetime of 1 year, i.e. effectively never expire. Since the package hash is part of the URL, cache
        # busting is automatic.
        headers={"Cache-Control": "public, immutable, max-age=31536000"},
    )
