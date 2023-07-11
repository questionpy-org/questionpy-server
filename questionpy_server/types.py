#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import Callable, Any, TypeVar, Awaitable

from pydantic import BaseModel


AwaitFuncT = Callable[..., Awaitable[Any]]

RouteHandler = TypeVar('RouteHandler', bound=AwaitFuncT)

M = TypeVar('M', bound=BaseModel)
