#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from asyncio import Lock
from pathlib import Path
from typing import Optional, overload, Union

from questionpy_server import WorkerPool
from questionpy_server.collector.abc import BaseCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.package import Package
from questionpy_server.utils.manfiest import ComparableManifest, SemVer


class Indexer:
    """Handles the indexing of packages which results in a faster lookup and fewer requests to the workers.

    Packages are indexed by their hash and by their identifier and version. If the package originates from an LMS, it is
    only indexed by its hash.
    """

    def __init__(self, worker_pool: WorkerPool):
        self._worker_pool = worker_pool

        self._index_by_hash: dict[str, Package] = {}
        self._index_by_identifier: dict[str, dict[SemVer, Package]] = {}
        """dict[identifier, dict[version, Package]]"""

        self._lock: Optional[Lock] = None

    def get_by_hash(self, package_hash: str) -> Optional[Package]:
        """Returns the package with the given hash or None if it does not exist.

        Args:
          package_hash (str): The hash of the package.

        Returns:
          The package or None.
        """

        return self._index_by_hash.get(package_hash, None)

    def get_by_identifier(self, identifier: str) -> dict[SemVer, Package]:
        """Returns a dict of packages with the given identifier and available versions.

        Args:
          identifier str: identifier of the package

        Returns:
          dict of packages and versions
        """

        return self._index_by_identifier.get(identifier, {}).copy()

    def get_by_identifier_and_version(self, identifier: str, version: SemVer) -> Optional[Package]:
        """Returns the package with the given identifier and version or None if it does not exist.

        Args:
          identifier (str): identifier of the package
          version (str): version of the package

        Returns:
          The package or None.
        """

        return self._index_by_identifier.get(identifier, {}).get(version, None)

    def get_packages(self) -> set[Package]:
        """Returns all packages in the index (excluding packages from LMSs).

        Returns:
            set of packages
        """

        return set(package for packages in self._index_by_identifier.values() for package in packages.values())

    @overload
    async def register_package(self, package_hash: str, path_or_manifest: ComparableManifest,
                               source: BaseCollector) -> Package:
        """Registers a package in the index.

        Args:
            package_hash (str): The hash of the package.
            path_or_manifest (Manifest): The manifest of the package.
            source (BaseCollector): The source of the package.
        """

    @overload
    async def register_package(self, package_hash: str, path_or_manifest: Path, source: BaseCollector) -> Package:
        """Registers a package in the index.

        Args:
            package_hash (str): The hash of the package.
            path_or_manifest (Manifest): The manifest of the package.
            source (BaseCollector): The source of the package.
        """

    async def register_package(self, package_hash: str, path_or_manifest: Union[Path, ComparableManifest],
                               source: BaseCollector) -> Package:
        if not self._lock:
            self._lock = Lock()

        async with self._lock:
            if package := self._index_by_hash.get(package_hash, None):
                # Package was already indexed; add source to package.
                package.sources.add(source)
            else:
                # Create new package...
                if isinstance(path_or_manifest, Path):
                    # ...from path.
                    async with self._worker_pool.get_worker(path_or_manifest, 0, None) as worker:
                        manifest = await worker.get_manifest()
                    package = Package(package_hash, manifest, source, path_or_manifest)
                else:
                    # ...from manifest.
                    package = Package(package_hash, path_or_manifest, source)
                self._index_by_hash[package.hash] = package

            # Check if package should be accessible by identifier and version.
            if isinstance(source, (LocalCollector, RepoCollector)):
                package_versions = self._index_by_identifier.setdefault(package.manifest.identifier, {})
                existing_package = package_versions.get(package.manifest.version, None)
                if existing_package and existing_package != package:
                    # Package with the same identifier and version already exists; log a warning.
                    log = logging.getLogger('questionpy-server:indexer')
                    log.warning("The package %s (%s) with hash: %s already exists with a different hash: %s.",
                                package.manifest.identifier, package.manifest.version, package.hash,
                                existing_package.hash)
                else:
                    package_versions[package.manifest.version] = package

        return package

    async def unregister_package(self, package_hash: str, source: BaseCollector) -> None:
        """Removes the given source from the package.
        If the only left source of the package is an LMS, it will only be
        accessible by its hash.
        If the package has no more sources, it is removed from the index.

        Args:
            package_hash (str): The hash of the package to unregister.
            source (BaseCollector): The source of the package.
        """

        package = self._index_by_hash.get(package_hash, None)
        if not package:
            return

        # Remove source from package.
        package.sources.remove(source)

        if isinstance(source, (LocalCollector, RepoCollector)) and not package.sources.contains_searchable():
            # Package should not be accessible by identifier and version (anymore).
            package_versions = self._index_by_identifier.get(package.manifest.identifier, None)
            if package_versions:
                # Remove package from index.
                package_versions.pop(package.manifest.version, None)
                # If there are no more packages with the same identifier, remove the identifier from the index.
                if not package_versions:
                    self._index_by_identifier.pop(package.manifest.identifier, None)

        if len(package.sources) == 0:
            # Package has no more sources; remove it from the index.
            self._index_by_hash.pop(package_hash, None)
