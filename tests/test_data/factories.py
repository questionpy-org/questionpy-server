#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import Callable
from typing import Any

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel
from semver import Version

from questionpy_common.manifest import Bcp47LanguageTag, PartialPackagePermissions
from questionpy_server.repository.models import RepoMeta, RepoPackageVersions
from questionpy_server.utils.manifest import ComparableManifest


class CustomFactory[T: BaseModel](ModelFactory[T]):
    """Custom factory base class adding support for :class:`Version` fields."""

    __is_base_factory__ = True

    @classmethod
    def get_provider_map(cls) -> dict[Any, Callable[[], Any]]:
        return {**super().get_provider_map(), Version: lambda: cls.__faker__.numerify(text="#.#.#")}


class RepoMetaFactory(ModelFactory[RepoMeta]): ...


class RepoPackageVersionsFactory(CustomFactory[RepoPackageVersions]): ...


class ManifestFactory(CustomFactory[ComparableManifest]):
    __set_as_default_factory_for_type__ = True

    short_name = Use(lambda: ModelFactory.__faker__.word().lower() + "_sn")
    namespace = Use(lambda: ModelFactory.__faker__.word().lower() + "_ns")
    name = {Bcp47LanguageTag("en"): "Factory Package"}
    languages = [Bcp47LanguageTag("en")]
    url = Use(ModelFactory.__faker__.url)
    icon = None
    permissions = PartialPackagePermissions()
    state_version = 0
    possible_side_migrations: dict[str, dict[str, int]] = {}
