from asyncio import Lock
from time import time
from typing import Optional, Iterable, TYPE_CHECKING

from questionpy_server.package import Package

if TYPE_CHECKING:
    from questionpy_server.collector.abc import FixedCollector


class Indexer:
    """
    Handles the indexing of packages which results in a faster lookup and fewer requests to the workers.

    Packages are indexed by their hash and by their name and version. If the package originates from an LMS, it is only
    indexed by its hash.
    """

    def __init__(self, collectors: Iterable['FixedCollector'], update_interval: int = 30):
        self._collectors = collectors

        self._index_by_hash: dict[str, Package] = {}
        self._index_by_name: dict[str, dict[str, Package]] = {}

        self._update_interval = update_interval
        self._last_update: float = 0.0

        self._lock = Lock()

    async def get_by_hash(self, package_hash: str) -> Optional[Package]:
        """
        Returns the package with the given hash or None if it does not exist.

        :param package_hash: The hash of the package.
        :return: The package or None.
        """

        await self.update()
        return self._index_by_hash.get(package_hash, None)

    async def get_by_name(self, short_name: str) -> dict[str, Package]:
        """
        Returns a dict of packages with the given short name and available versions.

        :param short_name: short name of the package
        :return: dict of packages and versions
        """

        await self.update()
        return self._index_by_name.get(short_name, {}).copy()

    async def get_by_name_and_version(self, short_name: str, version: str) -> Optional[Package]:
        """
        Returns the package with the given short name and version or None if it does not exist.

        :param short_name: short name of the package
        :param version: version of the package
        :return: The package or None.
        """

        await self.update()
        return self._index_by_name.get(short_name, {}).get(version, None)

    async def get_packages(self) -> set[Package]:
        """
        Returns all packages in the index (excluding packages from LMSs).

        :return: set of packages
        """

        await self.update()
        # TODO: change return value to self._index_by_name (-> let lms handle same packages with different versions)?
        return set(package for packages in self._index_by_name.values() for package in packages.values())

    def register_package(self, package: Package, from_lms: bool = False) -> None:
        """
        Registers a package in the index.

        :param package: The package to register.
        :param from_lms: Whether the package originates from an LMS.
        """

        self._index_by_hash[package.hash] = package
        if not from_lms:
            self._index_by_name.setdefault(package.manifest.short_name, {})[package.manifest.version] = package

    def register_packages(self, packages: Iterable[Package], from_lms: bool = False) -> None:
        """
        Registers multiple packages in the index.

        :param packages: The packages to register.
        :param from_lms: Whether the packages originate from an LMS.
        """

        for package in packages:
            self.register_package(package, from_lms)

    def unregister_package(self, package_hash: str) -> None:
        """
        Unregisters a package from the index.

        :param package_hash: The hash of the package to unregister.
        """

        package = self._index_by_hash.get(package_hash, None)
        if package:
            self._index_by_hash.pop(package_hash, None)
            self._index_by_name.get(package.manifest.short_name, {}).pop(package.manifest.version, None)

    async def update(self, force: bool = False) -> None:
        """
        Updates the index.

        :param force: Whether to force an update.
        """

        if force or time() - self._last_update > self._update_interval:
            async with self._lock:
                self._last_update = time()
                self._index_by_hash = {}
                self._index_by_name = {}
                for collector in self._collectors:
                    collector_packages = await collector.get_packages()
                    self.register_packages(collector_packages)
