from dataclasses import dataclass
from datetime import datetime
from functools import total_ordering

from pydantic import BaseModel, PositiveInt
from questionpy_server.utils.manfiest import ComparableManifest, SemVer


class RepoMeta(BaseModel):
    timestamp: datetime
    size: PositiveInt
    sha256: str


@total_ordering
class RepoPackageVersion(BaseModel):
    version: SemVer
    api_version: str

    path: str
    size: PositiveInt
    sha256: str

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RepoPackageVersion):
            return NotImplemented
        return self.version < other.version

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RepoPackageVersion):
            return NotImplemented
        return self.version == other.version


class RepoPackageVersions(BaseModel):
    manifest: ComparableManifest
    versions: list[RepoPackageVersion]


class RepoPackageIndex(BaseModel):
    packages: list[RepoPackageVersions]


@dataclass
class RepoPackage:
    manifest: ComparableManifest

    path: str
    size: PositiveInt
    sha256: str

    @classmethod
    def combine(cls, manifest: ComparableManifest, repo_package_version: RepoPackageVersion) -> 'RepoPackage':
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
