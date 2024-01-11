#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from asyncio import to_thread
from gzip import decompress
from urllib.parse import urljoin

from questionpy_server.cache import FileLimitLRU, SizeError
from questionpy_server.repository.helper import download
from questionpy_server.repository.models import RepoMeta, RepoPackage, RepoPackageIndex
from questionpy_server.utils.logger import URLAdapter


class Repository:
    def __init__(self, url: str, cache: FileLimitLRU):
        self._url_base = url
        self._url_index = urljoin(self._url_base, 'PACKAGES.json.gz')
        self._url_meta = urljoin(self._url_base, 'META.json')

        self._cache = cache

        logger = logging.getLogger('questionpy-server:repository')
        self._log = URLAdapter(logger, {'url': self._url_base})

    async def get_meta(self) -> RepoMeta:
        """
        Downloads and verifies metadata.

        Returns:
            RepoMeta: Metadata
        """
        meta = await download(self._url_meta)
        # TODO: verify downloaded data
        return RepoMeta.model_validate_json(meta)

    async def get_packages(self, meta: RepoMeta) -> dict[str, RepoPackage]:
        """
        Downloads and verifies package index.

        Args:
            meta (RepoMeta): Metadata

        Returns:
            dict[str, RepoPackage]: package index, where keys are package hashes
        """
        try:
            # Try to get the index from cache.
            raw_index_zip_path = self._cache.get(meta.sha256)
            raw_index_zip = await to_thread(raw_index_zip_path.read_bytes)
        except FileNotFoundError:
            # Download and parse RepoPackageVersions.
            raw_index_zip = await download(self._url_index, size=meta.size, expected_hash=meta.sha256)
            try:
                await self._cache.put(meta.sha256, raw_index_zip)
            except SizeError:
                self._log.warning('Package index is too big to be cached.')

        raw_index = decompress(raw_index_zip)
        index = RepoPackageIndex.model_validate_json(raw_index)

        # Combine general manifest of a package with correct (api-)version.
        packages_dict: dict[str, RepoPackage] = {}
        for package in index.packages:
            for version in package.versions:
                if packages_dict.get(version.sha256) is not None:
                    continue
                packages_dict[version.sha256] = RepoPackage.combine(package.manifest, version)

        return packages_dict

    async def get_package(self, package: RepoPackage) -> bytes:
        """
        Download a specific package from the repository.

        Args:
            package (RepoPackage): repository package

        Returns:
            bytes: raw package bytes
        """

        url = urljoin(self._url_base, package.path)
        data = await download(url, size=package.size, expected_hash=package.sha256)
        return data
