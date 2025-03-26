#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from aiohttp import web

from questionpy_server import __version__
from questionpy_server.models import ServerStatus, Usage
from questionpy_server.web._utils import pydantic_json_response
from questionpy_server.web.app import QPyServer

status_routes = web.RouteTableDef()


@status_routes.get(r"/status")
async def get_server_status(request: web.Request) -> web.Response:
    """Get server status."""
    qpyserver = request.app[QPyServer.APP_KEY]
    status = ServerStatus(
        version=__version__,
        allow_lms_packages=qpyserver.settings.webservice.allow_lms_packages,
        max_package_size=qpyserver.settings.webservice.max_package_size,
        usage=Usage(
            requests_in_process=qpyserver.worker_pool.get_workers_in_use_count(),
            requests_in_queue=qpyserver.worker_pool.get_pending_worker_request_count(),
        ),
    )
    return pydantic_json_response(data=status, status=200)
