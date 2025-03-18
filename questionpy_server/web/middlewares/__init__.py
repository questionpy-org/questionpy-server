#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Iterable

from aiohttp.typedefs import Middleware

from questionpy_server.web.middlewares._authentication import auth_middleware
from questionpy_server.web.middlewares._error import error_middleware

__all__ = ["middlewares"]


middlewares: Iterable[Middleware] = (auth_middleware, error_middleware)
