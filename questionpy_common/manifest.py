from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel


class PackageType(str, Enum):
    LIBRARY = 'LIBRARY'
    QUESTIONTYPE = 'QUESTIONTYPE'
    QUESTION = 'QUESTION'


class Manifest(BaseModel):
    short_name: str
    version: str
    api_version: str
    author: str
    name: dict[str, str] = {}
    entrypoint: str = "__main__"
    url: Optional[str] = None
    languages: set[str] = set()
    description: dict[str, str] = {}
    icon: Optional[str] = None
    type: PackageType = PackageType.QUESTIONTYPE
    license: Optional[str] = None
    permissions: set[str] = set()
    tags: set[str] = set()
    requirements: Optional[Union[str, list[str]]] = None
