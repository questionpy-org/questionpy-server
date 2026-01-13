from collections.abc import Iterable, Iterator, Mapping, Sequence

import resolvelib
from resolvelib.structs import Matches, RequirementInformation
from semver import Version

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.dependencies import DynamicDependencySolution, StaticDependencySolution
from questionpy_common.manifest import AbstractDynamicQPyDependency, DistDynamicQPyDependency, DistStaticQPyDependency
from questionpy_common.version_specifiers import QPyDependencyVersionSpecifier
from questionpy_server.dependencies._dynamic_resolver_abc import (
    DynamicDependencyResolver,
)

from ._model import (
    Candidate,
    DynamicRequirement,
    Requirement,
    RootRequirementAndCandidate,
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
) -> tuple[Sequence[DynamicRequirement], Sequence[StaticRequirement], RootRequirementAndCandidate | None]:
    dynamic: list[DynamicRequirement] = []
    static: list[StaticRequirement] = []
    root: RootRequirementAndCandidate | None = None

    for req in reqs:
        if isinstance(req, DynamicRequirement):
            dynamic.append(req)
        elif isinstance(req, StaticRequirement):
            static.append(req)
        else:
            root = req

    return dynamic, static, root


def _do_dynamic_reqs_allow_candidate(dynamic_reqs: Sequence[DynamicRequirement], cand_version: str | Version) -> bool:
    if isinstance(cand_version, str):
        cand_version = Version.parse(cand_version)

    for dynamic_req in dynamic_reqs:
        allows = (dynamic_req.dep.include_prereleases or cand_version.prerelease is None) and (
            dynamic_req.dep.version is None or dynamic_req.dep.version.allows(cand_version)
        )
        if not allows:
            return False

    return True


def _find_static_matches(
    nssn: PackageNamespaceAndShortName,
    static_reqs: Sequence[StaticRequirement],
    dynamic_reqs: Sequence[DynamicRequirement],
) -> Iterable[StaticDependencySolution]:
    """When one or more static requirements exists for a package, check that they're the same and return solutions."""
    for static_req in static_reqs[1:]:
        # We only compare the hash, since future changes in the manifest format might lead to inconsequential
        # differences between the 'dependencies' fields.
        if static_req.dep.hash != static_reqs[0].dep.hash:
            # There are multiple _different_ static versions of the dependency required.
            return ()

    # All the static dependencies are equivalent.

    if not _do_dynamic_reqs_allow_candidate(dynamic_reqs, static_reqs[0].dep.version):
        # At least one dynamic dependency does not allow the static version.
        return ()

    return (
        StaticDependencySolution(
            nssn=nssn,
            owner=static_req.owner,
            hash=static_req.dep.hash,
            version=static_req.dep.version,
            dependencies=static_req.dep.dependencies,
        )
        for static_req in static_reqs
    )


def _find_dynamic_matches(
    nssn: PackageNamespaceAndShortName, dynamic_reqs: Sequence[DynamicRequirement], resolver: DynamicDependencyResolver
) -> Iterator[DynamicDependencySolution]:
    """When only dynamic requirements exist for a package, find all matching available package versions."""
    merged = _merge_dynamic_deps(*(req.dep for req in dynamic_reqs))

    # TODO: Use locked version if possible.
    # We sort from highest (i.e. latest) version to lowest (i.e. oldest), since resolvelib tries candidates in order.
    matching_package_versions = sorted(
        resolver.get_matching_versions(
            nssn=nssn,
            version_spec=merged.version,
            include_prereleases=merged.include_prereleases,
        ),
        key=lambda apv: apv.version,
        reverse=True,
    )

    return (
        DynamicDependencySolution(
            nssn=nssn,
            hash=apv.hash,
            version=apv.manifest.version,
            dependencies=apv.manifest.dependencies,
        )
        for apv in matching_package_versions
    )


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

        dynamic_reqs, static_reqs, root_req = _partition_reqs(
            info.requirement for info in information.get(identifier, ())
        )

        is_root = root_req is not None
        is_static = len(static_reqs) > 0

        if dynamic_reqs:
            merged = _merge_dynamic_deps(*(req.dep for req in dynamic_reqs))
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
        reqs = tuple(requirements.get(identifier, ()))
        incompatible_candidates = tuple(incompatibilities.get(identifier, ()))

        if not reqs:
            msg = f"There is no requirement on '{identifier}', why are we resolving it?"
            raise RuntimeError(msg)

        dynamic_reqs, static_reqs, root_req = _partition_reqs(reqs)

        if root_req:
            if root_req in incompatible_candidates:
                # The root requirement has for some reason been marked as incompatible in a previous backtracking round.
                return ()
            if static_reqs:
                # There is also a static dependency on the root package, which isn't allowed.
                return ()

            # If there is a dynamic dependency on the root package, it's always a cycle.
            # We could return () in that case, but letting the cycle check later on handle this will lead to a better
            # error message than we could generate here.
            if not _do_dynamic_reqs_allow_candidate(dynamic_reqs, root_req.version):
                # Of course, if the version doesn't match, we still prevent it.
                return ()

            return (root_req,)

        if static_reqs:
            return _find_static_matches(identifier, static_reqs, dynamic_reqs)

        # Only dynamic dependencies for this NSSN have so far been discovered.
        return _find_dynamic_matches(identifier, dynamic_reqs, self._dynamic_resolver)

    def is_satisfied_by(self, requirement: Requirement, candidate: Candidate) -> bool:
        if isinstance(requirement, StaticRequirement):
            # Static requirements are only satisfied by static candidates. As long as the hashes match, the owner
            # doesn't matter.
            return isinstance(candidate, StaticDependencySolution) and candidate.hash == requirement.dep.hash

        # The root requirement is only satisfied by the root candidate.
        if isinstance(requirement, RootRequirementAndCandidate):
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
