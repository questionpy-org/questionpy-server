from hashlib import sha256
from inspect import Parameter, signature, isclass
from pathlib import Path
from typing import Callable, List, Type, Tuple

from questionpy_common.constants import MiB

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


def calculate_hash(path: Path, chunk_size: int = 5 * MiB) -> str:
    """Calculate SHA256 hash of a file."""
    package_hash = sha256()

    with path.open('rb') as file:
        while chunk := file.read(chunk_size):
            package_hash.update(chunk)

    return package_hash.hexdigest()
