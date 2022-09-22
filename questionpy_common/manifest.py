from typing import Dict, List, Optional, Set, Union

from pydantic_yaml import YamlModel as _YamlModel, YamlStrEnum as _YamlStrEnum


class PackageType(_YamlStrEnum):
    QUESTION_TYPE = "QUESTION_TYPE"
    LIBRARY = "LIBRARY"


class Manifest(_YamlModel):
    short_name: str
    version: str
    api_version: str
    author: str
    name: Dict[str, str] = {}
    entrypoint: str = "__main__"
    url: Optional[str] = None
    languages: Set[str] = set()
    description: Dict[str, str] = {}
    icon: Optional[str] = None
    type: PackageType = PackageType.QUESTION_TYPE
    license: Optional[str] = None
    permissions: Set[str] = set()
    tags: Set[str] = set()
    requirements: Optional[Union[str, List[str]]]
