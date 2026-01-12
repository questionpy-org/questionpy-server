from collections.abc import Iterable

from resolvelib.structs import RequirementInformation

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.constants import MAX_QPY_DEPENDENCY_LEVELS
from questionpy_common.manifest import AbstractDynamicQPyDependency, DistStaticQPyDependency

from ._model import Candidate, Requirement, RootRequirementAndCandidate


def _dep_version_to_str(dep: AbstractDynamicQPyDependency | DistStaticQPyDependency) -> str:
    if isinstance(dep, AbstractDynamicQPyDependency):
        string = str(dep.version) if dep.version else "any version"
        string += " (including prereleases)" if dep.include_prereleases else " (excluding prereleases)"
        return string

    return f"statically packaged version {dep.version} ({dep.hash})"


def _tree_path_to_str(path: tuple[PackageNamespaceAndShortName, ...]) -> str:
    return " -> ".join(map(str, path))


class QPyDependencyError(Exception):
    pass


class DependencyConflictError(QPyDependencyError):
    def __init__(
        self, nssn: PackageNamespaceAndShortName, causes: Iterable[RequirementInformation[Requirement, Candidate]]
    ) -> None:
        msg = f"No version of '{nssn}' could be found that satisfies all of the following dependencies:"
        for req, parent in causes:
            if isinstance(req, RootRequirementAndCandidate):
                msg += f"\n\t- root package ({req.version})"
            else:
                parent_str = f"'{parent.nssn}:{parent.version}'" if parent else "unexpected top-level requirement"
                msg += f"\n\t- via {parent_str}: {_dep_version_to_str(req.dep)}"

        super().__init__(msg)
        self.nssn = nssn


class DependencyCycleError(QPyDependencyError):
    def __init__(self, path: tuple[PackageNamespaceAndShortName, ...]) -> None:
        msg = f"The dependency tree contains a cycle: {_tree_path_to_str(path)}"
        super().__init__(msg)

        self.path = path


class TooDeeplyNestedDependencyError(QPyDependencyError):
    def __init__(self, path: tuple[PackageNamespaceAndShortName, ...]) -> None:
        msg = f"Dependency graph is deeper than {MAX_QPY_DEPENDENCY_LEVELS} levels at {_tree_path_to_str(path)}."
        super().__init__(msg)
