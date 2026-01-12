import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import final

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.package_location import PackageLocation
from questionpy_common.version_specifiers import QPyDependencyVersionSpecifier
from questionpy_server.utils.manifest import Manifest, ParsableSemverVersion

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvailablePackageVersion:
    manifest: Manifest
    hash: str
    version: ParsableSemverVersion


class NoPackageWithHashError(Exception):
    def __init__(self, hash_: str) -> None:
        msg = f"Previously found package with hash '{hash_}' cannot be retrieved."
        super().__init__(msg)


class DynamicDependencyResolver(ABC):
    """Finds packages matching a given dynamic dependency.

    This is implemented using the `PackageCollection` in the server, but we also intend for the solver to be used by the
    SDK at build-time, so this is an ABC.
    """

    @abstractmethod
    def get_matching_versions(
        self,
        nssn: PackageNamespaceAndShortName,
        version_spec: QPyDependencyVersionSpecifier | None,
        *,
        include_prereleases: bool,
    ) -> Iterable[AvailablePackageVersion]:
        """Returns all package versions matching the given restrictions, in any order.

        When this resolver has no packages matching the given restrictions, no error is thrown, just an empty iterable
        returned.
        """

    @abstractmethod
    async def get_package_location(self, hash_: str) -> PackageLocation:
        """Gets a location for a package that was previously returned by `get_matching_versions`.

        Raises:
            NoPackageWithHashError
        """


@final
class NoopDependencyResolver(DynamicDependencyResolver):
    """A dependency resolver that does not provide any dependencies."""

    def get_matching_versions(
        self,
        nssn: PackageNamespaceAndShortName,
        version_spec: QPyDependencyVersionSpecifier | None,
        *,
        include_prereleases: bool,
    ) -> Iterable[AvailablePackageVersion]:
        return ()

    async def get_package_location(self, hash_: str) -> PackageLocation:
        raise NoPackageWithHashError(hash_)
