import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from semver import Version

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.version_specifiers import QPyDependencyVersionSpecifier
from questionpy_server.utils.manifest import Manifest, ParsableSemverVersion

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvailablePackageVersion:
    manifest: Manifest
    hash: str
    version: ParsableSemverVersion


def _format_dependency(nssn: PackageNamespaceAndShortName, version_spec: QPyDependencyVersionSpecifier | None) -> str:
    return f"@{nssn.namespace}/{nssn.short_name}{' ' + str(version_spec) if version_spec else ''}"


class NoPackageMatchingVersionSpecError(Exception):
    def __init__(
        self,
        nssn: PackageNamespaceAndShortName,
        version_spec: QPyDependencyVersionSpecifier | None,
        available_versions: Sequence[Version],
        *,
        include_prereleases: bool,
    ) -> None:
        msg = f"No package found for '{_format_dependency(nssn, version_spec)}'."

        latest = max(available_versions, default=None)
        if latest is None:
            msg += " There are no versions of that package available."
        else:
            msg += f" There are {len(available_versions)} versions available, of which '{latest}' is the latest."

        if include_prereleases:
            msg += " (Including prereleases.)"
        else:
            msg += " (Excluding prereleases.)"

        super().__init__(msg)

        self.nssn = nssn
        self.version_spec = version_spec
        self.include_prereleases = include_prereleases
        self.available_versions = available_versions


class DynamicDependencyResolver(ABC):
    """Finds packages matching a given dynamic dependency.

    This is implemented using the `PackageCollection` in the server, but we also intend for the solver to be used by the
    SDK at build-time, so this is an ABC.
    """

    @abstractmethod
    def resolve_all(
        self,
        nssn: PackageNamespaceAndShortName,
        version_spec: QPyDependencyVersionSpecifier | None,
        *,
        include_prereleases: bool,
    ) -> Iterable[AvailablePackageVersion]:
        pass
