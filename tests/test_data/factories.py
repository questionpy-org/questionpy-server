from typing import Any

from pydantic_factories import ModelFactory

from questionpy_server.repository.models import RepoMeta, RepoPackageVersions
from questionpy_server.utils.manfiest import ComparableManifest, SemVer


class CustomFactory(ModelFactory[Any]):
    @classmethod
    def get_mock_value(cls, field_type: Any) -> Any:
        if field_type is SemVer:
            return cls.get_faker().numerify(text='#.#.#')
        return super().get_mock_value(field_type)


class RepoMetaFactory(ModelFactory):
    __model__ = RepoMeta


class RepoPackageVersionsFactory(CustomFactory):
    __model__ = RepoPackageVersions


class ManifestFactory(CustomFactory):
    __model__ = ComparableManifest
