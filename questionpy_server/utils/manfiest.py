#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from typing import Union, Iterator, Callable, Any

from pydantic.json import custom_pydantic_encoder
from semver import VersionInfo as _Version

from questionpy_common.manifest import Manifest


class SemVer(_Version):
    @classmethod
    def _parse(cls, version: Union[str, bytes]) -> 'SemVer':
        if isinstance(version, cls):
            return version
        return cls.parse(version)

    @classmethod
    def __get_validators__(cls) -> Iterator[Callable[[Union[str, bytes]], 'SemVer']]:
        yield cls._parse


class ComparableManifest(Manifest):
    version: SemVer  # type: ignore[assignment]

    class Config:
        json_encoders = {
            SemVer: str
        }


def semver_encoder(obj: Any) -> Any:
    return custom_pydantic_encoder({SemVer: str}, obj)
