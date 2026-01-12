from dataclasses import dataclass

from semver import Version

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.dependencies import DynamicDependencySolution, StaticDependencySolution
from questionpy_common.manifest import AbstractDynamicQPyDependency, DistDependencies, DistStaticQPyDependency


@dataclass(frozen=True)
class DynamicRequirement:
    dep: AbstractDynamicQPyDependency

    @property
    def nssn(self) -> PackageNamespaceAndShortName:
        return self.dep.nssn


@dataclass(frozen=True)
class StaticRequirement:
    owner: PackageNamespaceAndShortName
    dep: DistStaticQPyDependency

    @property
    def nssn(self) -> PackageNamespaceAndShortName:
        return self.dep.nssn


@dataclass(frozen=True)
class RootPackage:
    """Represents the root package as both a requirement and a candidate."""

    nssn: PackageNamespaceAndShortName
    version: Version
    dependencies: DistDependencies


type Requirement = DynamicRequirement | StaticRequirement | RootPackage


type DynamicCandidate = DynamicDependencySolution
type StaticCandidate = StaticDependencySolution

type Candidate = DynamicCandidate | StaticCandidate | RootPackage
