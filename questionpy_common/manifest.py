import typing as _typing

import pydantic_yaml as _pydantic_yaml


class PackageType(_pydantic_yaml.YamlStrEnum):
    QUESTION_TYPE = "QUESTION_TYPE"
    LIBRARY = "LIBRARY"


class Manifest(_pydantic_yaml.YamlModel):
    short_name: str
    version: str
    api_version: str
    author: str
    name: _typing.Dict[str, str] = {}
    entrypoint: str = "__main__"
    url: _typing.Optional[str] = None
    languages: _typing.Set[str] = set()
    description: _typing.Dict[str, str] = {}
    icon: _typing.Optional[str] = None
    type: PackageType = PackageType.QUESTION_TYPE
    license: _typing.Optional[str] = None
    permissions: _typing.Set[str] = set()
    tags: _typing.Set[str] = set()
    requirements: _typing.Optional[_typing.Union[str, _typing.List[str]]]
