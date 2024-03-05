#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from questionpy_server.worker.worker import Worker

AwaitFuncT = Callable[..., Awaitable[Any]]

RouteHandler = TypeVar("RouteHandler", bound=AwaitFuncT)

M = TypeVar("M", bound=BaseModel)

WorkerType = type[Worker]
