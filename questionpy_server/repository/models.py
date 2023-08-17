#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from dataclasses import dataclass
from datetime import datetime
from functools import total_ordering

from pydantic import BaseModel, PositiveInt
from questionpy_server.utils.manifest import ComparableManifest, SemVer


class RepoMeta(BaseModel):
    """Metadata of the repository."""
    repository_schema_version: int
    """Version of the repository index schema."""
    timestamp: datetime
    """Timestamp of the repository index creation."""
    size: PositiveInt
    """Size of the compressed repository index in bytes."""
    sha256: str
    """SHA256 hash of the compressed repository index."""


@total_ordering
class RepoPackageVersion(BaseModel):
    """Represents a specific version of a package in the repository."""
    version: SemVer
    """Version of the package."""
    api_version: str
    """Compatible API version of the package."""

    path: str
    """Relative path to the package inside the repository."""
    size: PositiveInt
    """Size of the package in bytes."""
    sha256: str
    """SHA256 hash of the package."""

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RepoPackageVersion):
            return NotImplemented
        return self.version < other.version

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RepoPackageVersion):
            return NotImplemented
        return self.version == other.version


class RepoPackageVersions(BaseModel):
    """Represents a package with all its versions in the repository."""
    manifest: ComparableManifest
    """Manifest of the most recent version of the package."""
    versions: list[RepoPackageVersion]
    """List of all versions of the package."""


class RepoPackageIndex(BaseModel):
    """Represents the index of the repository."""
    packages: list[RepoPackageVersions]
    """List of all available packages in the repository."""


@dataclass
class RepoPackage:
    """Represents a package in the repository."""
    manifest: ComparableManifest
    """Manifest of the package."""

    path: str
    """Path to the package inside the repository."""
    size: PositiveInt
    """Size of the package in bytes."""
    sha256: str
    """SHA256 hash of the package."""

    @classmethod
    def combine(cls, manifest: ComparableManifest, repo_package_version: RepoPackageVersion) -> 'RepoPackage':
        """
        Combines the manifest of a package with a specific version of that package.

        Args:
            manifest: manifest of the most recent version of the package
            repo_package_version: version of the package
        """
        # Replace package version and api version with actual versions.
        modified_manifest = manifest.copy(deep=True)
        modified_manifest.version = repo_package_version.version
        modified_manifest.api_version = repo_package_version.api_version

        return cls(
            manifest=modified_manifest,
            path=repo_package_version.path,
            size=repo_package_version.size,
            sha256=repo_package_version.sha256
        )
