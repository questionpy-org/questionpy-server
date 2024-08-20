#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

from questionpy_server.api.models import PackageVersionInfo
from questionpy_server.collector.abc import BaseCollector
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.utils.manifest import ComparableManifest

if TYPE_CHECKING:
    from questionpy_server.collector.abc import BaseCollector


class PackageSources:
    """A container for all package sources."""

    def __init__(self, package: "Package"):
        self._package = package

        self._local_collector: LocalCollector | None = None
        self._repo_collectors: list[RepoCollector] = []
        self._lms_collector: LMSCollector | None = None

    def __len__(self) -> int:
        local_collector = 1 if self._local_collector else 0
        lms_collector = 1 if self._lms_collector else 0
        return local_collector + len(self._repo_collectors) + lms_collector

    def add(self, collector: "BaseCollector") -> None:
        """Adds a collector to the package sources.

        Args:
            collector (BaseCollector): The collector to add.
        """
        if isinstance(collector, LocalCollector):
            self._local_collector = collector
        elif isinstance(collector, RepoCollector):
            self._repo_collectors.append(collector)
        elif isinstance(collector, LMSCollector):
            self._lms_collector = collector
        else:
            msg = f"Invalid collector type: {type(collector)}"
            raise TypeError(msg)

    def remove(self, collector: "BaseCollector") -> None:
        """Removes a collector from the package sources.

        Args:
            collector (BaseCollector): The collector to remove.
        """
        if isinstance(collector, LocalCollector):
            self._local_collector = None
        elif isinstance(collector, RepoCollector):
            with contextlib.suppress(ValueError):
                self._repo_collectors.remove(collector)
        elif isinstance(collector, LMSCollector):
            self._lms_collector = None
        else:
            msg = f"Invalid collector type: {type(collector)}"
            raise TypeError(msg)

    async def get_path(self) -> Path:
        """Returns the path to the package.

        Goes through all available collectors and tries to retrieve a path to the package in the following order:
        1. LocalCollector
        2. RepoCollectors
        3. LMSCollector

        Returns:
            The path to the package.
        """
        if self._local_collector:
            try:
                return await self._local_collector.get_path(self._package)
            except FileNotFoundError:
                pass

        for collector in self._repo_collectors:
            try:
                return await collector.get_path(self._package)
            except FileNotFoundError:
                continue

        if self._lms_collector:
            await self._lms_collector.get_path(self._package)

        raise FileNotFoundError

    def contains_searchable(self) -> bool:
        return bool(self._local_collector or self._repo_collectors)


class Package:
    hash: str
    manifest: ComparableManifest

    sources: PackageSources

    _info: PackageVersionInfo | None
    _path: Path | None

    def __init__(
        self,
        package_hash: str,
        manifest: ComparableManifest,
        source: "BaseCollector | None" = None,
        path: Path | None = None,
    ):
        self.hash = package_hash
        self.manifest = manifest

        self.sources = PackageSources(self)
        if source:
            self.sources.add(source)

        self._info = None
        self._path = path

    def __hash__(self) -> int:
        return hash(self.hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Package):
            return NotImplemented
        return self.hash == other.hash

    def get_info(self) -> PackageVersionInfo:
        """Returns the package info.

        Returns:
            The package info.
        """
        if not self._info:
            tmp = self.manifest.model_dump()
            tmp["version"] = str(tmp["version"])
            self._info = PackageVersionInfo(**tmp, package_hash=self.hash)
        return self._info

    async def get_path(self) -> Path:
        """Returns the path to the package.

        Returns:
            The path to the package.
        """
        if not (self._path and self._path.is_file()):
            self._path = await self.sources.get_path()
        return self._path
