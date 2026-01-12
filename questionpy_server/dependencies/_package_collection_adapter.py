from collections.abc import Iterable

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.package_location import PackageLocation
from questionpy_common.version_specifiers import QPyDependencyVersionSpecifier
from questionpy_server.collector import PackageCollection

from ._dynamic_resolver_abc import (
    AvailablePackageVersion,
    DynamicDependencyResolver,
    NoPackageWithHashError,
)


class PackageCollectionDependencyResolver(DynamicDependencyResolver):
    """A dependency resolver backed by the QPy server's `PackageCollection`."""

    def __init__(self, package_collection: PackageCollection) -> None:
        self._package_collection = package_collection

    def get_matching_versions(
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

    async def get_package_location(self, hash_: str) -> PackageLocation:
        package = self._package_collection.get(hash_)
        if not package:
            raise NoPackageWithHashError(hash_)

        return await package.get_zip_package_location()
