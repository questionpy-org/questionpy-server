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

    def __str__(self) -> str:
        string = str(self.dep.version) if self.dep.version else "any version"
        string += " (including prereleases)" if self.dep.include_prereleases else " (excluding prereleases)"
        return string


@dataclass(frozen=True)
class StaticRequirement:
    owner: PackageNamespaceAndShortName
    dep: DistStaticQPyDependency

    @property
    def nssn(self) -> PackageNamespaceAndShortName:
        return self.dep.nssn

    def __str__(self) -> str:
        return f"statically packaged version {self.dep.version} ({self.dep.hash})"


@dataclass(frozen=True)
class RootRequirementAndCandidate:
    """Represents the root package as both a requirement and a candidate."""

    nssn: PackageNamespaceAndShortName
    version: Version
    dependencies: DistDependencies

    def __str__(self) -> str:
        return f"root package ({self.nssn}:{self.version})"


type Requirement = DynamicRequirement | StaticRequirement | RootRequirementAndCandidate


type DynamicCandidate = DynamicDependencySolution
type StaticCandidate = StaticDependencySolution

type Candidate = DynamicCandidate | StaticCandidate | RootRequirementAndCandidate
