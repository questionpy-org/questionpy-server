from collections.abc import Iterable

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.version_specifiers import QPyDependencyVersionSpecifier
from questionpy_server.collector import PackageCollection
from questionpy_server.utils.manifest import Manifest
from questionpy_server.worker.runtime.package_location import PackageLocation

from ._dynamic_resolver_abc import (
    AvailablePackageVersion,
    DynamicDependencyResolver,
)
from ._solutions import (
    DependencySolution,
    DynamicDependencySolution,
    StaticDependencySolution,
)
from ._solver import resolve_dependency_tree


class _PackageCollectionDependencyResolver(DynamicDependencyResolver):
    def __init__(self, package_collection: PackageCollection) -> None:
        self._package_collection = package_collection

    def resolve_all(
        self,
        nssn: PackageNamespaceAndShortName,
        version_spec: QPyDependencyVersionSpecifier | None,
        *,
        include_prereleases: bool,
    ) -> Iterable[AvailablePackageVersion]:
        versions = self._package_collection.get_by_identifier(str(nssn))

        return tuple(
            AvailablePackageVersion(package.manifest, package.hash, version)
            for version, package in versions.items()
            if (include_prereleases or version.prerelease is None)
            and (version_spec is None or version_spec.allows(version))
        )


type SolutionAndLocation = tuple[DynamicDependencySolution, PackageLocation] | tuple[StaticDependencySolution, None]


class WorkerDependencyResolver:
    """A server-specific wrapper for the generic solver.

    Uses the `PackageCollection` to implement the `DynamicDependencyResolver`.
    """

    def __init__(self, package_collection: PackageCollection) -> None:
        self._package_collection = package_collection
        self._dynamic_resolver = _PackageCollectionDependencyResolver(package_collection)

    async def _resolve_if_dynamic(self, solution: DependencySolution) -> SolutionAndLocation:
        if isinstance(solution, StaticDependencySolution):
            return solution, None

        package = self._package_collection.get(solution.hash)
        if not package:
            # This is a race condition that is technically possible, but probably quite unlikely.
            msg = f"Package '{solution.hash}' was just resolved, but cannot be found (anymore)."
            raise RuntimeError(msg)

        return solution, await package.get_zip_package_location()

    async def resolve_and_retrieve(
        self, root_manifest: Manifest
    ) -> dict[PackageNamespaceAndShortName, SolutionAndLocation]:
        """Solves the dependency tree and gets `PackageLocation`s for all dynamic solutions."""
        solutions = resolve_dependency_tree(root_manifest, root_manifest.dependencies.qpy, self._dynamic_resolver)

        return {nssn: await self._resolve_if_dynamic(solution) for nssn, solution in solutions.items()}
