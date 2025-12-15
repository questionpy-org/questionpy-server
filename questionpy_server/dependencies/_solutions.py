from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.constants import RE_SEMVER
from questionpy_common.manifest import DistDependencies


@dataclass(frozen=True)
class StaticDependencySolution:
    """Indicates that a package in the tree provides a static dependency that is to be used.

    Usually, this is a solution for the static dependency itself, but if there is also a dynamic dependency in the tree
    for that NSSN _and_ that dynamic dependency allows the static version, a `StaticDependencySolution` might be used to
    also solve a dynamic dependency.

    If multiple packages provide the same version of a static dependency, any of them may be used as the solution.
    Static dependencies on different versions of the same NSSN will always lead to a `DependencyConflictError`.
    """

    nssn: PackageNamespaceAndShortName

    owner: PackageNamespaceAndShortName
    """The package that includes this static dependency."""

    hash: str
    # semver.Version is avoided to allow solutions to be passed to the package.
    version: Annotated[str, Field(pattern=RE_SEMVER)]

    dependencies: DistDependencies = field(compare=False)
    """Transitive dependencies of this dependency."""

    def __str__(self) -> str:
        return f"{self.hash} ({self.version}, statically packaged in '{self.owner}')"


@dataclass(frozen=True)
class DynamicDependencySolution:
    """Indicates that the given version should be used to supply all usages of the NSSN."""

    nssn: PackageNamespaceAndShortName

    hash: str
    # semver.Version is avoided to allow solutions to be passed to the package.
    version: Annotated[str, Field(pattern=RE_SEMVER)]
    dependencies: DistDependencies = field(compare=False)
    """Transitive dependencies of this dependency."""

    def __str__(self) -> str:
        return f"{self.hash} ({self.version}, dynamic)"


type DependencySolution = StaticDependencySolution | DynamicDependencySolution
