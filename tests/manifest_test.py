from typing import Any, Dict

import pytest
from pydantic import ValidationError

from questionpy_common.manifest import Manifest, PackageType

minimal_manifest: Dict[str, Any] = {'short_name': 'short_name', 'version': '0.1.0', 'api_version': '0.1.0',
                                    'author': 'John Doe'}
maximal_manifest = {**minimal_manifest, 'name': {'en': 'test_name'}, 'entrypoint': 'test_entrypoint',
                    'url': 'https://example.com/package', 'languages': {'en'},
                    'description': {'en': 'test_description'}, 'icon': 'https://example.com/icon.png',
                    'type': PackageType.QUESTIONTYPE, 'license': 'MIT', 'permissions': {'test_permission'},
                    'tags': {'test_tag'}, 'requirements': ['req_1', 'req_2']}


@pytest.mark.parametrize("data", (
    # minimal manifest
    minimal_manifest,
    # 'requirements' is a string
    {**minimal_manifest, 'requirements': 'req'},
    # 'requirements' is a list
    {**minimal_manifest, 'requirements': ['req_1', 'req_2']},
    # maximal manifest
    maximal_manifest,
))
def test_valid_manifest(data: dict[str, Any]) -> None:
    Manifest(**data)


@pytest.mark.parametrize("data", (
    minimal_manifest,
    maximal_manifest,
))
def test_ignore_additional_properties(data: dict[str, Any]) -> None:
    manifest = Manifest(**data, additional_property='test')
    assert not hasattr(manifest, 'additional_property')


@pytest.mark.parametrize("data, error_message", (
    # no manifest
    [{}, r'4 validation errors for \w'],
    # 'name' is not a dict
    [{**minimal_manifest, 'name': 'test_name'}, r'1 validation error for \w'],
    # 'type' is not a valid PackageType
    [{**minimal_manifest, 'type': 'NOT_VALID'}, r'1 validation error for \w'],
    # 'requirements' is not a string or list
    [{**minimal_manifest, 'requirements': {'req_1': 1, 'req_2': 2}}, r'2 validation errors for \w'],
))
def test_not_valid_manifest(data: dict[str, Any], error_message: str) -> None:
    with pytest.raises(ValidationError, match=error_message):
        Manifest(**data)
