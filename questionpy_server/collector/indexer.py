import logging
from asyncio import Lock
from pathlib import Path
from typing import Optional, overload, Union

from questionpy_common.manifest import Manifest

from questionpy_server import WorkerPool
from questionpy_server.collector.abc import BaseCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.package import Package


class Indexer:
    """
    Handles the indexing of packages which results in a faster lookup and fewer requests to the workers.

    Packages are indexed by their hash and by their name and version. If the package originates from an LMS, it is only
    indexed by its hash.
    """

    def __init__(self, worker_pool: WorkerPool):
        self._worker_pool = worker_pool

        self._index_by_hash: dict[str, Package] = {}
        self._index_by_name: dict[str, dict[str, Package]] = {}

        # TODO: initialize Lock here if the minimum supported Python version is 3.10 or above
        self._lock: Optional[Lock] = None

    def get_by_hash(self, package_hash: str) -> Optional[Package]:
        """
        Returns the package with the given hash or None if it does not exist.

        :param package_hash: The hash of the package.
        :return: The package or None.
        """

        return self._index_by_hash.get(package_hash, None)

    def get_by_name(self, short_name: str) -> dict[str, Package]:
        """
        Returns a dict of packages with the given short name and available versions.

        :param short_name: short name of the package
        :return: dict of packages and versions
        """

        return self._index_by_name.get(short_name, {}).copy()

    def get_by_name_and_version(self, short_name: str, version: str) -> Optional[Package]:
        """
        Returns the package with the given short name and version or None if it does not exist.

        :param short_name: short name of the package
        :param version: version of the package
        :return: The package or None.
        """

        return self._index_by_name.get(short_name, {}).get(version, None)

    def get_packages(self) -> set[Package]:
        """
        Returns all packages in the index (excluding packages from LMSs).

        :return: set of packages
        """

        return set(package for packages in self._index_by_name.values() for package in packages.values())

    @overload
    async def register_package(self, package_hash: str, path_or_manifest: Manifest, source: BaseCollector) -> Package:
        """
        Registers a package in the index.

        :param package_hash: The hash of the package.
        :param path_or_manifest: The manifest of the package.
        :param source: The source of the package.
        """

    @overload
    async def register_package(self, package_hash: str, path_or_manifest: Path, source: BaseCollector) -> Package:
        """
        Registers a package in the index.

        :param package_hash: The hash of the package.
        :param path_or_manifest: The path to the package.
        :param source: The source of the package.
        """

    async def register_package(self, package_hash: str, path_or_manifest: Union[Path, Manifest],
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

            # Check if package should be accessible by name and version.
            if isinstance(source, (LocalCollector, RepoCollector)):
                package_versions = self._index_by_name.setdefault(package.manifest.short_name, {})
                existing_package = package_versions.get(package.manifest.version, None)
                if existing_package and existing_package != package:
                    # Package with the same short_name and version already exists; log a warning.
                    log = logging.getLogger('questionpy-server:indexer')
                    log.warning("The package %s (%s) with hash: %s already exists with a different hash: %s.",
                                package.manifest.short_name, package.manifest.version, package.hash,
                                existing_package.hash)
                else:
                    package_versions[package.manifest.version] = package

        return package

    async def unregister_package(self, package_hash: str, source: BaseCollector) -> None:
        """
        Removes the given source from the package. If the only left source of the package is an LMS, it will only be
        accessible by its hash. If the package has no more sources, it is removed from the index.

        :param package_hash: The hash of the package to unregister.
        :param source: The source of the package.
        """

        package = self._index_by_hash.get(package_hash, None)
        if not package:
            return

        # Remove source from package.
        package.sources.remove(source)

        if isinstance(source, (LocalCollector, RepoCollector)) and not package.sources.contains_searchable():
            # Package should not be accessible by name and version (anymore).
            package_versions = self._index_by_name.get(package.manifest.short_name, None)
            if package_versions:
                # Remove package from index.
                package_versions.pop(package.manifest.version, None)
                # If there are no more packages with the same name, remove the name from the index.
                if not package_versions:
                    self._index_by_name.pop(package.manifest.short_name, None)

        if len(package.sources) == 0:
            # Package has no more sources; remove it from the index.
            self._index_by_hash.pop(package_hash, None)
