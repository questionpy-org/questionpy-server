#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from typing import NamedTuple

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


def get_matching[T: Selectable](selectables: list[T], query: SelectorQuery) -> T | None:
    """Gets the first matching selectable, if any.

    It assumes that the selectables are ordered from least specific to most specific.
    """
    for selectable in reversed(selectables):
        if _is_matching(selectable.package_selector, query):
            return selectable
    return None
