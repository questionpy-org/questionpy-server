# pylint: disable=redefined-outer-name

from json import dumps
from pathlib import Path
from unittest.mock import patch
from gzip import compress
from urllib.parse import urljoin

import pytest

from questionpy_server.repository import Repository, RepoMeta, RepoPackage, RepoPackageIndex
from questionpy_server.utils.manfiest import ComparableManifest, semver_encoder
from tests.test_data.factories import RepoMetaFactory, RepoPackageVersionsFactory, ManifestFactory


REPO_URL = 'https://example.com/repo/'


@pytest.fixture
def repository() -> Repository:
    return Repository(REPO_URL)


async def test_get_meta(repository: Repository) -> None:
    with patch('questionpy_server.repository.download') as mock:
        expected = RepoMetaFactory.build()
        mock.return_value = expected.json().encode()

        # Get meta.
        meta = await repository.get_meta()

        # Check if correct url gets called.
        url = urljoin(REPO_URL, 'META.json')
        mock.assert_called_once_with(url)

        assert meta == expected


async def test_get_packages(repository: Repository) -> None:
    package_versions_0 = {
        'manifest': {
            'short_name': 'package_0',
            'namespace': 'namespace_0',
        },
        'versions': [{'sha256': '0', 'version': '1.0.0', 'api_version': '1.0'},
                     {'sha256': '1', 'version': '2.0.0', 'api_version': '2.0'}],
    }

    package_versions_1 = {
        'manifest': {
            'short_name': 'package_1',
            'namespace': 'namespace_1',
        },
        'versions': [{'sha256': '2', 'version': '3.0.0', 'api_version': '3.0'}],
    }

    package_index = RepoPackageIndex(packages=[
                        RepoPackageVersionsFactory().build(**package_versions_0),  # type: ignore[arg-type]
                        RepoPackageVersionsFactory().build(**package_versions_1)   # type: ignore[arg-type]
                    ])

    with patch('questionpy_server.repository.download') as mock:
        parsed = dumps(package_index, default=semver_encoder)
        mock.return_value = compress(parsed.encode())

        # Get packages.
        meta: RepoMeta = RepoMetaFactory.build()
        index = await repository.get_packages(meta)

        # Check if correct url gets called.
        url = urljoin(REPO_URL, 'PACKAGES.json.gz')
        mock.assert_called_once_with(url, size=meta.size, expected_hash=meta.sha256)

        # There should be 3 packages and the keys should be the hashes.
        assert {'0', '1', '2'} == set(index)

        for packages in package_index.packages:
            for versions in packages.versions:
                package = index[versions.sha256]

                # Combine manifest with version and api_version.
                expected_manifest = packages.manifest.dict()
                expected_manifest['version'] = str(versions.version)
                expected_manifest['api_version'] = versions.api_version

                # Check if the combined manifest is correct.
                assert package.manifest == ComparableManifest(**expected_manifest)


async def test_get_package(repository: Repository) -> None:
    manifest = ManifestFactory.build(short_name='package', namespace='namespace')
    package_path = Path('path/to/package.qpy')
    package = RepoPackage(manifest=manifest, sha256='hash', size=1, path=package_path)
    with patch('questionpy_server.repository.download') as mock:
        mock.return_value = b'package'

        # Get package.
        data = await repository.get_package(package)

        # Check if correct url gets called.
        url = urljoin(REPO_URL, str(package_path))
        mock.assert_called_once_with(url, size=package.size, expected_hash=package.sha256)

        assert data == b'package'
