#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from hashlib import sha256
from inspect import Parameter, signature, isclass
from pathlib import Path
from typing import Callable, List, Type, Tuple, Union

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


def calculate_hash(source: Union[bytes, Path]) -> str:
    """
    Calculates the sha256 of either bytes or a file.

    :param source: bytes or path to file
    :return: the sha256
    """
    sha = sha256()

    if isinstance(source, bytes):
        sha.update(source)
    else:
        with source.open('rb') as file:
            while chunk := file.read(5 * MiB):
                sha.update(chunk)

    return sha.hexdigest()
