import logging
from collections.abc import Mapping
from typing import NamedTuple

import resolvelib
from resolvelib.resolvers import Criterion
from resolvelib.structs import State

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.constants import MAX_QPY_DEPENDENCY_LEVELS

from ._model import (
    Candidate,
    Requirement,
    RootRequirementAndCandidate,
)
from .errors import DependencyCycleError, TooDeeplyNestedDependencyError


def _tree_path_to_str(path: tuple[PackageNamespaceAndShortName, ...]) -> str:
    return " -> ".join(map(str, path))


class QPyResolvelibReporter(resolvelib.BaseReporter[Requirement, Candidate, PackageNamespaceAndShortName]):
    def __init__(self, root_nssn: PackageNamespaceAndShortName) -> None:
        self._root_nssn = root_nssn
        self._logger = logging.getLogger(__name__)

        self._messages: list[str] = []

    def pinning(self, candidate: Candidate) -> None:
        if isinstance(candidate, RootRequirementAndCandidate):
            # Not very interesting...
            return

        # The solution classes have decent __str__ methods.
        self._messages.append(f"Tentatively resolved '{candidate.nssn}' to {candidate}.")

    def rejecting_candidate(self, criterion: Criterion[Requirement, Candidate], candidate: Candidate) -> None:
        self._messages.append(f"Rejecting previously pinned resolution of '{candidate.nssn}' to {candidate}.")

    def _format_messages(self) -> str:
        return "\n".join(f"\t- {message}" for message in self._messages)

    def ending(self, state: State[Requirement, Candidate, PackageNamespaceAndShortName]) -> None:
        # Resolvelib can deal with cycles in some cases, but we (the package initialization in the worker) cannot.
        cycle, longest_path = _find_cycle_and_longest_path(state.mapping, self._root_nssn)

        if cycle is None:
            self._messages.append("The tree was successfully resolved to a consistent and acyclic graph.")
        else:
            cycle_as_str = _tree_path_to_str(cycle)
            # log_failed_resolution will be called by the exception handler.
            self._messages.append(
                f"The tree was resolved to a consistent graph, but it contains a cycle: {cycle_as_str}"
            )

            raise DependencyCycleError(cycle)

        if len(longest_path) > MAX_QPY_DEPENDENCY_LEVELS:
            raise TooDeeplyNestedDependencyError(longest_path)

    def log_successful_resolution(self) -> None:
        # The resolver automatically calls the 'ending' method, but we want to check
        # This is called by the resolver automatically when the resolution ends successfully.

        summary = f"Successfully resolved dependency tree of package '{self._root_nssn}'."

        if self._logger.isEnabledFor(logging.DEBUG):
            # Detailed output.
            self._logger.debug("%s The following steps were taken:\n%s", summary, self._format_messages())
        else:
            # Just the summary.
            self._logger.info(summary)

    def log_failed_resolution(self, error: Exception) -> None:
        # This isn't called by the resolver, we call it when the resolution raises an exception.

        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(
                "Failed to resolve dependency tree of package '%s'. The following steps were taken:\n%s",
                self._root_nssn,
                self._format_messages(),
                exc_info=error,
            )


class _GraphCycleAndLongestPath(NamedTuple):
    first_cycle: tuple[PackageNamespaceAndShortName, ...] | None
    longest_path: tuple[PackageNamespaceAndShortName, ...]


def _find_cycle_and_longest_path(
    mapping: Mapping[PackageNamespaceAndShortName, Candidate], root_nssn: PackageNamespaceAndShortName
) -> _GraphCycleAndLongestPath:
    """Performs a depth-first search to find the first cycle and the longest path starting from `root_nssn`."""
    seen = set[PackageNamespaceAndShortName]()
    longest_path: tuple[PackageNamespaceAndShortName, ...] = (root_nssn,)

    def recursive_dfs(
        path: tuple[PackageNamespaceAndShortName, ...],
    ) -> tuple[PackageNamespaceAndShortName, ...] | None:
        node = path[-1]
        seen.add(node)
        candidate = mapping[node]

        for dep in candidate.dependencies.qpy:
            new_path = (*path, dep.nssn)

            nonlocal longest_path
            if len(new_path) > len(longest_path):
                longest_path = new_path

            if len(set(new_path)) != len(new_path):
                # There is a cycle up to this dependency.
                return new_path

            if dep.nssn not in seen:
                cycle = recursive_dfs(new_path)
                if cycle is not None:
                    return cycle

        return None

    return _GraphCycleAndLongestPath(recursive_dfs((root_nssn,)), longest_path)
