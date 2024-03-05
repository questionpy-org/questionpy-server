import functools
from typing import TYPE_CHECKING, Any, Callable, cast, get_type_hints

from aiohttp.abc import Request
from aiohttp.log import web_logger
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound, HTTPUnsupportedMediaType

from questionpy_server.api.models import MainBaseModel, NotFoundStatus, NotFoundStatusWhat
from questionpy_server.types import RouteHandler
from questionpy_server.web import create_model_from_json, get_or_save_package, parse_form_data

if TYPE_CHECKING:
    from questionpy_server.app import QPyServer


def ensure_package_and_question_state_exist(
    _func: RouteHandler | None = None,
) -> RouteHandler | Callable[[RouteHandler], RouteHandler]:
    """Decorator function used to ensure that the package and question state exist (if needed by func) and that the json
    corresponds to the model given as a type annotation in func.

    This decorator assumes that:
      * func may want an argument named 'data' (with a subclass of MainBaseModel)
      * func may want an argument named 'question_state' (bytes or Optional[bytes])
      * every func wants a package with an argument named 'package'

    Args:
        _func (Optional[RouteHandler]): Control parameter; allows using the decorator with or without arguments.
            If this decorator is used with any arguments, this will always be the decorated function itself.
            (Default value = None)
    """

    def decorator(function: RouteHandler) -> RouteHandler:
        """Internal decorator function."""
        type_hints = get_type_hints(function)
        question_state_type = type_hints.get("question_state")
        takes_question_state = question_state_type is not None
        require_question_state = question_state_type is bytes
        main_part_json_model: type[MainBaseModel] | None = type_hints.get("data")

        if main_part_json_model:
            assert issubclass(
                main_part_json_model, MainBaseModel
            ), f"Parameter 'data' of function {function.__name__} has unexpected type."

        @functools.wraps(function)
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            """Wrapper around the actual function call."""
            server: "QPyServer" = request.app["qpy_server_app"]
            package_hash: str = request.match_info.get("package_hash", "")

            if request.content_type == "multipart/form-data":
                main, sent_package, sent_question_state = await parse_form_data(request)
            elif request.content_type == "application/json":
                main, sent_package, sent_question_state = await request.read(), None, None
            else:
                web_logger.info("Wrong content type, multipart/form-data expected, got %s", request.content_type)
                raise HTTPUnsupportedMediaType

            if main_part_json_model:
                if main is None:
                    msg = "Multipart/form-data field 'main' is not set"
                    web_logger.warning(msg)
                    raise HTTPBadRequest(text=msg)

                model = create_model_from_json(main.decode(), main_part_json_model)
                kwargs["data"] = model

            # Check if func wants a question state and if it is provided.
            if takes_question_state:
                if require_question_state and sent_question_state is None:
                    msg = "Multipart/form-data field 'question_state' is not set"
                    web_logger.warning(msg)
                    raise HTTPBadRequest(text=msg)
                kwargs["question_state"] = sent_question_state

            # Check if a package is provided and if it matches the optional hash given in the URL.
            if sent_package and package_hash and package_hash != sent_package.hash:
                msg = f"Package hash does not match: {package_hash} != {sent_package.hash}"
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            package = await get_or_save_package(server.package_collection, package_hash, sent_package)
            if package is None:
                if package_hash:
                    raise HTTPNotFound(
                        text=NotFoundStatus(what=NotFoundStatusWhat.PACKAGE).model_dump_json(),
                        content_type="application/json",
                    )

                msg = "No package found in multipart/form-data"
                web_logger.warning(msg)
                raise HTTPBadRequest(text=msg)

            kwargs["package"] = package
            return await function(request, *args, **kwargs)

        return cast(RouteHandler, wrapper)

    if _func is None:
        return decorator
    return decorator(_func)
