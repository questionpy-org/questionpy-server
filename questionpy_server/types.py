from typing import Callable, Any, TypeVar, Awaitable

from pydantic import BaseModel


AwaitFuncT = Callable[..., Awaitable[Any]]

RouteHandler = TypeVar('RouteHandler', bound=AwaitFuncT)

M = TypeVar('M', bound=BaseModel)
