#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import TYPE_CHECKING

from aiohttp import web

from questionpy_server import __version__
from questionpy_server.api.models import ServerStatus, Usage
from questionpy_server.web import json_response

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer


status_routes = web.RouteTableDef()


@status_routes.get(r"/status")
async def get_server_status(request: web.Request) -> web.Response:
    """Get server status."""
    qpyserver: QPyServer = request.app["qpy_server_app"]
    status = ServerStatus(
        version=__version__,
        allow_lms_packages=qpyserver.settings.webservice.allow_lms_packages,
        max_package_size=qpyserver.settings.webservice.max_package_size,
        usage=Usage(
            requests_in_process=await qpyserver.worker_pool.get_requests_in_process(),
            requests_in_queue=await qpyserver.worker_pool.get_requests_in_queue(),
        ),
    )
    return json_response(data=status, status=200)
