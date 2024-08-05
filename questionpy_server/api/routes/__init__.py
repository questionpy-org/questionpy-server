#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from ._attempts import attempt_routes
from ._files import file_routes
from ._packages import package_routes
from ._status import status_routes

routes = (*attempt_routes, *file_routes, *package_routes, *status_routes)
