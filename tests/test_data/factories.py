#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Callable
from typing import Any

from polyfactory.factories.pydantic_factory import ModelFactory
from semver import Version

from questionpy_server.repository.models import RepoMeta, RepoPackageVersions
from questionpy_server.utils.manifest import ComparableManifest


class CustomFactory(ModelFactory[Any]):
    """Custom factory base class adding support for :class:`Version` fields."""

    __is_base_factory__ = True

    @classmethod
    def get_provider_map(cls) -> dict[Any, Callable[[], Any]]:
        return {**super().get_provider_map(), Version: lambda: cls.__faker__.numerify(text="#.#.#")}


class RepoMetaFactory(ModelFactory):
    __model__ = RepoMeta


class RepoPackageVersionsFactory(CustomFactory):
    __model__ = RepoPackageVersions


class ManifestFactory(CustomFactory):
    __model__ = ComparableManifest
