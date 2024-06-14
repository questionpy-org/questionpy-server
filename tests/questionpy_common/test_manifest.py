#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import Any

import pytest
from pydantic import ValidationError

from questionpy_common.manifest import Manifest, PackageType

minimal_manifest: dict[str, Any] = {
    "short_name": "short_name",
    "version": "0.1.0",
    "api_version": "0.1",
    "author": "John Doe",
}
maximal_manifest = {
    **minimal_manifest,
    "name": {"en": "test_name"},
    "entrypoint": "test_entrypoint",
    "url": "https://example.com/package",
    "languages": {"en"},
    "description": {"en": "test_description"},
    "icon": "https://example.com/icon.png",
    "type": PackageType.QUESTIONTYPE,
    "license": "MIT",
    "permissions": {"test_permission"},
    "tags": {"test_tag"},
    "requirements": ["req_1", "req_2"],
}


@pytest.mark.parametrize(
    "data",
    [
        # minimal manifest
        minimal_manifest,
        # 'requirements' is a string
        {**minimal_manifest, "requirements": "req"},
        # 'requirements' is a list
        {**minimal_manifest, "requirements": ["req_1", "req_2"]},
        # maximal manifest
        maximal_manifest,
    ],
)
def test_valid_manifest(data: dict[str, Any]) -> None:
    Manifest(**data)


@pytest.mark.parametrize(
    "data",
    [
        minimal_manifest,
        maximal_manifest,
    ],
)
def test_ignore_additional_properties(data: dict[str, Any]) -> None:
    manifest = Manifest(**data, additional_property="test")
    assert not hasattr(manifest, "additional_property")


@pytest.mark.parametrize(
    ("data", "error_message"),
    [
        # no manifest
        ({}, r"4 validation errors for \w"),
        # 'name' is not a dict
        ({**minimal_manifest, "name": "test_name"}, r"1 validation error for \w"),
        # 'type' is not a valid PackageType
        ({**minimal_manifest, "type": "NOT_VALID"}, r"1 validation error for \w"),
        # 'requirements' is not a string or list
        ({**minimal_manifest, "requirements": {"req_1": 1, "req_2": 2}}, r"2 validation errors for \w"),
    ],
)
def test_not_valid_manifest(data: dict[str, Any], error_message: str) -> None:
    with pytest.raises(ValidationError, match=error_message):
        Manifest(**data)


@pytest.mark.parametrize("field", ["short_name", "namespace"])
@pytest.mark.parametrize("name", ["default", "a_name", "_name", "name_", "_name_", "_a_name_", "a" * 127])
def test_valid_name(field: str, name: str) -> None:
    manifest = minimal_manifest.copy()
    manifest[field] = name
    Manifest(**manifest)


@pytest.mark.parametrize("field", ["short_name", "namespace"])
@pytest.mark.parametrize(
    ("name", "error_message"),
    [
        ("", "can not be empty"),
        ("notValid", "can only contain lowercase alphanumeric characters and underscores"),
        (" not_valid", "can only contain lowercase alphanumeric characters and underscores"),
        ("not_valid ", "can only contain lowercase alphanumeric characters and underscores"),
        ("not-valid", "can only contain lowercase alphanumeric characters and underscores"),
        ("not~valid", "can only contain lowercase alphanumeric characters and underscores"),
        ("not valid", "can only contain lowercase alphanumeric characters and underscores"),
        ("\u03c0", "can only contain lowercase alphanumeric characters and underscores"),
        ("a" * 128, "can have at most 127 characters"),
        ("42", "can not start with a digit"),
        ("def", "can not be a Python keyword"),
        ("class", "can not be a Python keyword"),
        ("global", "can not be a Python keyword"),
        ("match", "can not be a Python keyword"),
        ("_", "can not be a Python keyword"),
    ],
)
def test_not_valid_name(field: str, name: str, error_message: str) -> None:
    error = f"1 validation error for Manifest\n{field}\n  Value error, {error_message}"
    manifest = minimal_manifest.copy()
    manifest[field] = name
    with pytest.raises(ValidationError, match=error):
        Manifest(**manifest)


@pytest.mark.parametrize("version", ["0.1", "1.0", "10.1", "2023.4"])
def test_valid_api_version(version: str) -> None:
    manifest = minimal_manifest.copy()
    manifest["api_version"] = version
    Manifest(**manifest)


@pytest.mark.parametrize(
    "version",
    [
        "1",
        ".1",
        "1.",
        "01.0" "0.01",
        "-1.0",
        "1.0-",
        "1.-1",
        "1.0.",
        ".1.0",
        "0.1.0",
        "v1.0",
        "v1.0.0",
        "V1.0" "V1.0.0",
        "1.0-alpha",
        "version",
    ],
)
def test_not_valid_api_version(version: str) -> None:
    error = "1 validation error for Manifest\napi_version\n*"
    manifest = minimal_manifest.copy()
    manifest["api_version"] = version
    with pytest.raises(ValidationError, match=error):
        Manifest(**manifest)
