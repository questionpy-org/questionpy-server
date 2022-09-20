from inspect import Parameter, signature, isclass
from typing import Callable, List, Type, Tuple

from questionpy_server.types import RouteHandler, M


def get_parameters_of_type(function: Callable, cls: type) -> List[Parameter]:
    output = []
    param: Parameter
    for _, param in signature(function).parameters.items():
        if isclass(param.annotation) and issubclass(param.annotation, cls):
            output.append(param)
    return output


def get_route_model_param(route_handler: RouteHandler, model: Type[M]) -> Tuple[str, Type[M]]:
    params = get_parameters_of_type(route_handler, model)
    if len(params) == 0:
        raise Exception(f"No parameter of the type `{model.__name__}` present in function "
                        f"`{route_handler.__name__}`.")
    if len(params) > 1:
        raise Exception(f"More than one parameter of the type `{model.__name__}` present in function "
                        f"`{route_handler.__name__}`.")
    return params[0].name, params[0].annotation
