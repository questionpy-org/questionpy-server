from collections.abc import Sequence

import resolvelib
from resolvelib import ResolutionImpossible, ResolutionTooDeep
from semver import Version

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.dependencies import DependencySolution
from questionpy_common.manifest import (
    DistDependencies,
    DistQPyDependency,
    SourceManifest,
)
from questionpy_server.dependencies._dynamic_resolver_abc import DynamicDependencyResolver

from ._model import RootRequirementAndCandidate
from ._provider import QPyResolvelibProvider
from ._reporter import QPyResolvelibReporter
from .errors import DependencyConflictError, QPyDependencyError


def resolve_dependency_tree(
    root: SourceManifest,
    root_dependencies: Sequence[DistQPyDependency],
    dynamic_dep_resolver: DynamicDependencyResolver,
) -> dict[PackageNamespaceAndShortName, DependencySolution]:
    """Finds solutions for all packages in the dependency tree of the given root package.

    Raises:
        DependencyConflictError: If different requirements for a package conflict.
        TooDeeplyNestedDependencyError: If MAX_QPY_DEPENDENCY_LEVELS is exceeded.
        DependencyCycleError: If there is a cycle in the dependency tree after resolution.
        QPyDependencyError: If the dependency tree cannot be resolved at all. (Which may also be due to some kinds of
                            cycles.)
    """
    provider = QPyResolvelibProvider(dynamic_dep_resolver)
    reporter = QPyResolvelibReporter(root.nssn)
    resolver = resolvelib.Resolver(provider, reporter)

    root_node = RootRequirementAndCandidate(
        root.nssn, Version.parse(root.version), DistDependencies(qpy=list(root_dependencies))
    )

    try:
        result = resolver.resolve((root_node,))
    except Exception as e:
        reporter.log_failed_resolution(e)

        if isinstance(e, QPyDependencyError):
            raise

        if isinstance(e, ResolutionImpossible):
            causes = tuple(e.causes)
            if not causes:
                msg = "ResolutionImpossible without causes"
                raise QPyDependencyError(msg) from e

            nssn = causes[0].requirement.nssn
            raise DependencyConflictError(nssn, causes) from e

        if isinstance(e, ResolutionTooDeep):
            msg = f"Dependency resolution took too many ({e.round_count}) rounds."
            raise QPyDependencyError(msg) from e

        msg = "Unknown resolution error"
        raise QPyDependencyError(msg) from e
    else:
        reporter.log_successful_resolution()

    return {
        nssn: candidate
        for nssn, candidate in result.mapping.items()
        if not isinstance(candidate, RootRequirementAndCandidate)
    }
