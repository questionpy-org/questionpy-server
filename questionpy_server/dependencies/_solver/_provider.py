from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import cast

import resolvelib
from resolvelib.structs import Matches, RequirementInformation
from semver import Version

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.manifest import AbstractDynamicQPyDependency, DistDynamicQPyDependency, DistStaticQPyDependency
from questionpy_common.version_specifiers import QPyDependencyVersionSpecifier
from questionpy_server.dependencies._dynamic_resolver_abc import (
    DynamicDependencyResolver,
)
from questionpy_server.dependencies._solutions import (
    DependencySolution,
    DynamicDependencySolution,
    StaticDependencySolution,
)

from ._model import (
    Candidate,
    DynamicRequirement,
    Requirement,
    RootPackage,
    StaticRequirement,
)


class _MergedDynamicDep(AbstractDynamicQPyDependency):
    pass


def _merge_dynamic_deps(dep: AbstractDynamicQPyDependency, *deps: AbstractDynamicQPyDependency) -> _MergedDynamicDep:
    clauses = list(dep.version.clauses) if dep.version else []
    include_prereleases = dep.include_prereleases

    for other_dep in deps:
        if isinstance(other_dep, AbstractDynamicQPyDependency):
            if other_dep.version:
                clauses.extend(other_dep.version.clauses)
            include_prereleases &= other_dep.include_prereleases

    return _MergedDynamicDep(
        namespace=dep.namespace,
        short_name=dep.short_name,
        version=QPyDependencyVersionSpecifier(clauses) if clauses else None,
        include_prereleases=include_prereleases,
    )


def _partition_reqs(
    reqs: Iterable[Requirement],
) -> tuple[Sequence[DynamicRequirement], Sequence[StaticRequirement]]:
    dynamic: list[DynamicRequirement] = []
    static: list[StaticRequirement] = []

    for req in reqs:
        if isinstance(req, DynamicRequirement):
            dynamic.append(req)
        elif isinstance(req, StaticRequirement):
            static.append(req)

    return dynamic, static


def _find_solutions(
    nssn: PackageNamespaceAndShortName,
    reqs: Iterable[DynamicRequirement | StaticRequirement],
    resolver: DynamicDependencyResolver,
) -> Iterable[DependencySolution]:
    dynamic_reqs, static_reqs = _partition_reqs(reqs)

    if static_reqs:
        for static_req in static_reqs[1:]:
            # We only compare the hash, since future changes in the manifest format might lead to inconsequential
            # differences between the 'dependencies' fields.
            if static_req.dep.hash != static_reqs[0].dep.hash:
                # There are multiple _different_ static versions of the dependency required.
                return ()

        # All the static dependencies are equivalent. We'll use the first.
        chosen_static_req = static_reqs[0]
        chosen_static_version = Version.parse(chosen_static_req.dep.version)

        for dynamic_req in dynamic_reqs:
            if dynamic_req.dep.version and not dynamic_req.dep.version.allows(chosen_static_version):
                # At least one dynamic dependency does not allow the static version.
                return ()

        return (
            StaticDependencySolution(
                nssn=nssn,
                owner=chosen_static_req.owner,
                hash=chosen_static_req.dep.hash,
                version=chosen_static_req.dep.version,
                dependencies=chosen_static_req.dep.dependencies,
            ),
        )

    # Only dynamic dependencies for this NSSN have so far been discovered.
    merged = _merge_dynamic_deps(*(req.dep for req in dynamic_reqs))

    # TODO: Use locked version if possible.
    matching_package_versions = resolver.resolve_all(
        nssn=nssn,
        version_spec=merged.version,
        include_prereleases=merged.include_prereleases,
    )

    return (
        DynamicDependencySolution(
            nssn=nssn,
            hash=available_package.hash,
            version=available_package.manifest.version,
            dependencies=available_package.manifest.dependencies,
        )
        for available_package in matching_package_versions
    )


# Implement logic so the resolver understands the requirement format.
class QPyResolvelibProvider(resolvelib.AbstractProvider[Requirement, Candidate, PackageNamespaceAndShortName]):
    def __init__(self, dynamic_resolver: DynamicDependencyResolver) -> None:
        self._dynamic_resolver = dynamic_resolver

    def identify(self, requirement_or_candidate: Requirement | Candidate) -> PackageNamespaceAndShortName:
        return requirement_or_candidate.nssn

    def get_preference(
        self,
        identifier: PackageNamespaceAndShortName,
        resolutions: Mapping[PackageNamespaceAndShortName, Candidate],
        candidates: Mapping[PackageNamespaceAndShortName, Iterator[Candidate]],
        information: Mapping[PackageNamespaceAndShortName, Iterator[RequirementInformation[Requirement, Candidate]]],
        backtrack_causes: Sequence[RequirementInformation[Requirement, Candidate]],
    ) -> tuple[bool, bool, bool, bool, PackageNamespaceAndShortName]:
        # This method only serves to optimize the resolution by resolving more restricted packages first.
        # In our case, we resolve in the following order:
        # - root package
        # - static dependencies
        # - dynamic dependencies with at least one "==" constraint
        # - dynamic dependencies with any constraints
        # - dynamic dependencies without constraints
        #
        # Within those groups, we use alphabetical order, for consistency.
        # This strategy is inspired by pip.

        static_deps: list[DistStaticQPyDependency] = []
        dynamic_deps: list[AbstractDynamicQPyDependency] = []

        is_root = False
        for info in information.get(identifier, ()):
            if isinstance(info.requirement, DynamicRequirement):
                dynamic_deps.append(info.requirement.dep)
            elif isinstance(info.requirement, StaticRequirement):
                static_deps.append(info.requirement.dep)
            else:
                is_root = True

        is_static = bool(static_deps)

        if dynamic_deps:
            merged = _merge_dynamic_deps(*dynamic_deps)
            is_pinned = any(clause.operator == "==" for clause in merged.version.clauses) if merged.version else False
            is_restricted = merged.version is not None and len(merged.version.clauses) > 0
        else:
            is_pinned = False
            is_restricted = False

        return (
            not is_root,
            not is_static,
            not is_pinned,
            not is_restricted,
            identifier,
        )

    def find_matches(
        self,
        identifier: PackageNamespaceAndShortName,
        requirements: Mapping[PackageNamespaceAndShortName, Iterator[Requirement]],
        incompatibilities: Mapping[PackageNamespaceAndShortName, Iterator[Candidate]],
    ) -> Matches[Candidate]:
        reqs = list(requirements.get(identifier, ()))
        incompatible_candidates = list(incompatibilities.get(identifier, ()))

        root_req = next((req for req in reqs if isinstance(req, RootPackage)), None)
        if root_req:
            if root_req in incompatible_candidates:
                return ()
            return (root_req,)

        # If we're here, then there is no root requirement. (i.e., this is not the root package.)

        return sorted(
            (
                solution
                for solution in _find_solutions(
                    identifier, cast("list[DynamicRequirement | StaticRequirement]", reqs), self._dynamic_resolver
                )
                if solution not in incompatible_candidates
            ),
            key=lambda solution: solution.version,
            reverse=True,
        )

    def is_satisfied_by(self, requirement: Requirement, candidate: Candidate) -> bool:
        if isinstance(requirement, StaticRequirement):
            # Static requirements are only satisfied by static candidates. As long as the hashes match, the owner
            # doesn't matter.
            return isinstance(candidate, StaticDependencySolution) and candidate.hash == requirement.dep.hash

        # The root requirement is only satisfied by the root candidate.
        if isinstance(requirement, RootPackage):
            return requirement == candidate

        # Dynamic requirements can be satisfied by any kind of candidate so long as the versions match.
        parsed_version = Version.parse(candidate.version) if isinstance(candidate.version, str) else candidate.version
        return (requirement.dep.include_prereleases or parsed_version.prerelease is None) and (
            requirement.dep.version is None or requirement.dep.version.allows(parsed_version)
        )

    def get_dependencies(self, candidate: Candidate) -> Iterable[Requirement]:
        for dep in candidate.dependencies.qpy:
            if isinstance(dep, DistDynamicQPyDependency):
                yield DynamicRequirement(dep)
            elif isinstance(dep, DistStaticQPyDependency):
                yield StaticRequirement(candidate.nssn, dep)
