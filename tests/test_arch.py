import sys

from pytest_archon import archrule

import questionpy_common
import questionpy_server.worker.runtime

STD_MODULES_PATTERN = [f"{module}*" for module in sys.stdlib_module_names]


def test_questionpy_common_should_only_import_pydantic() -> None:
    (
        archrule("questionpy_common_should_only_import_pydantic")
        .match("*")
        .should_not_import("*")
        .may_import(*STD_MODULES_PATTERN)
        .may_import("pydantic*")
        .may_import("questionpy_common*")
        .check(questionpy_common)
    )


def test_questionpy_worker_runtime_should_only_import_pydantic_and_questionpy_common() -> None:
    (
        archrule("questionpy_worker_runtime_should_only_import_pydantic_and_questionpy_common")
        .match("*")
        .should_not_import("*")
        .may_import(*STD_MODULES_PATTERN)
        .may_import("pydantic*")
        .may_import("questionpy_common*")
        .may_import("questionpy_server.worker.runtime*")
        .check(questionpy_server.worker.runtime)
    )
