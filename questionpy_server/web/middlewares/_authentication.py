#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from hashlib import sha256

from aiohttp import BasicAuth, hdrs, web
from aiohttp.typedefs import Handler
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

from questionpy_server.settings import AuthSettings
from questionpy_server.web._utils import CURRENT_USER_KEY

PASSWORD_ENCODING = "utf-8"  # noqa: S105


class HTTPUnauthorizedBasicAuth(web.HTTPUnauthorized):
    """HTTP 401 Unauthorized error for BasicAuth."""

    def __init__(self, reason: str | None = None):
        super().__init__(reason=reason, headers={hdrs.WWW_AUTHENTICATE: 'Basic realm="api"'})


def get_auth_settings(request: Request) -> AuthSettings:
    from questionpy_server.web.app import QPyServer  # noqa: PLC0415

    qpyserver = request.app[QPyServer.APP_KEY]
    return qpyserver.settings.auth


def get_credentials(request: Request) -> BasicAuth:
    """Returns the BasicAuth object from the request."""
    header = request.headers.get(hdrs.AUTHORIZATION)
    if header is None:
        raise HTTPUnauthorizedBasicAuth(reason="Missing authorization header")

    try:
        return BasicAuth.decode(header, encoding=PASSWORD_ENCODING)
    except ValueError as error:
        raise HTTPUnauthorizedBasicAuth(reason="Invalid authorization header") from error


def check_credentials(credentials: BasicAuth, users: dict[str, str]) -> bool:
    """Checks if the given credentials are correct."""
    if credentials.login not in users:
        return False

    try:
        password_hash = sha256(credentials.password.encode(encoding=PASSWORD_ENCODING)).hexdigest()
        return users[credentials.login] == password_hash
    except UnicodeEncodeError:
        return False


@web.middleware
async def auth_middleware(request: Request, handler: Handler) -> StreamResponse:
    """Handles authentication."""
    settings = get_auth_settings(request)
    if not settings.enabled:
        return await handler(request)

    credentials = get_credentials(request)
    if check_credentials(credentials, settings.users):
        request[CURRENT_USER_KEY] = credentials.login
        return await handler(request)

    raise HTTPUnauthorizedBasicAuth(reason="Invalid credentials")
