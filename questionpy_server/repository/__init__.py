from gzip import decompress
from urllib.parse import urljoin

from pydantic import parse_raw_as

from questionpy_server.repository.helper import download
from questionpy_server.repository.models import RepoMeta, RepoPackage, RepoPackageIndex


class Repository:
    def __init__(self, url: str):
        self._url_base = url
        self._url_index = urljoin(self._url_base, 'PACKAGES.json.gz')
        self._url_meta = urljoin(self._url_base, 'META.json')

    async def get_meta(self) -> RepoMeta:
        """
        Downloads and verifies metadata.

        :return: metadata
        """
        meta = await download(self._url_meta)
        # TODO: verify downloaded data
        return parse_raw_as(RepoMeta, meta)

    async def get_packages(self, meta: RepoMeta) -> dict[str, RepoPackage]:
        """
        Downloads and verifies package index.

        :param meta: metadata
        :return: package index, where keys are package hashes
        """
        # Download and parse RepoPackageVersions.
        index_zip = await download(self._url_index, size=meta.size, expected_hash=meta.sha256)
        index_bytes = decompress(index_zip)
        index = parse_raw_as(RepoPackageIndex, index_bytes)

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

        :param package: repository package
        :return: raw package bytes
        """

        url = urljoin(self._url_base, package.path)
        data = await download(url, size=package.size, expected_hash=package.sha256)
        return data
