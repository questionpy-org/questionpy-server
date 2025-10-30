#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import ABC, abstractmethod
from typing import NamedTuple

from questionpy_server.cache import LRUCacheMemory
from questionpy_server.package import Package
from questionpy_server.settings import PackageSelector, Selectable


class SelectorQuery(NamedTuple):
    package: Package
    user: str | None
    context: str


def _is_wildcard_matching(selector_value: str, package_value: str) -> bool:
    return selector_value in {package_value, "*"}


def _is_matching(selector: PackageSelector, query: SelectorQuery) -> bool:
    return (
        # Package data.
        _is_wildcard_matching(selector.hash, query.package.hash)
        and _is_wildcard_matching(selector.namespace, query.package.manifest.namespace)
        and _is_wildcard_matching(selector.short_name, query.package.manifest.short_name)
        and (selector.version == "*" or query.package.manifest.version.match(selector.version))
        # Package origin.
        and _is_wildcard_matching(selector.origin.repositories, "*")  # TODO: handle repositories
        and (selector.origin.local is None or selector.origin.local == query.package.sources.is_local())
        and _is_wildcard_matching(selector.origin.users, "*")  # TODO: handle users
        # Request data.
        and _is_wildcard_matching(selector.request_user, str(query.user) if query.user else "")
        and _is_wildcard_matching(selector.request_context, query.context)
    )


class Selector[T: Selectable, V](ABC):
    def __init__(self, selectables: list[T]):
        self._cache: LRUCacheMemory[SelectorQuery, V] = LRUCacheMemory(max_size=128)
        self._selectables = selectables

    def _get_matching(self, query: SelectorQuery) -> T | None:
        for selectable in reversed(self._selectables):
            if _is_matching(selectable.package_selector, query):
                return selectable
        return None

    def get(self, query: SelectorQuery) -> V:
        if cached_environment_variables := self._cache.get(query):
            return cached_environment_variables

        result = self._get(query)
        self._cache.put(query, result)

        return result

    @abstractmethod
    def _get(self, query: SelectorQuery) -> V: ...
