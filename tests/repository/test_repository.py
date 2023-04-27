# pylint: disable=redefined-outer-name

from json import dumps
from unittest.mock import patch, Mock, ANY
from gzip import compress
from urllib.parse import urljoin

from _pytest.tmpdir import TempPathFactory

from questionpy_common.constants import KiB

from questionpy_server.cache import FileLimitLRU
from questionpy_server.repository import Repository, RepoMeta, RepoPackage, RepoPackageIndex
from questionpy_server.utils.manfiest import ComparableManifest, semver_encoder
from tests.test_data.factories import RepoMetaFactory, RepoPackageVersionsFactory, ManifestFactory


REPO_URL = 'https://example.com/repo/'


async def test_get_meta() -> None:
    repository = Repository(REPO_URL, Mock())
    with patch('questionpy_server.repository.download') as mock:
        expected = RepoMetaFactory.build()
        mock.return_value = expected.json().encode()

        # Get meta.
        meta = await repository.get_meta()

        # Check if correct url gets called.
        url = urljoin(REPO_URL, 'META.json')
        mock.assert_called_once_with(url)

        assert meta == expected


async def test_get_packages(tmp_path_factory: TempPathFactory) -> None:
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

    repository = Repository(REPO_URL, FileLimitLRU(tmp_path_factory.mktemp('qpy'), 100 * KiB))

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


async def test_get_packages_cached(tmp_path_factory: TempPathFactory) -> None:
    package_versions = {
        'manifest': {
            'short_name': 'package_1',
            'namespace': 'namespace_1',
        },
        'versions': [{'sha256': '2', 'version': '3.0.0', 'api_version': '3.0'}],
    }

    cache = FileLimitLRU(tmp_path_factory.mktemp('qpy'), 100 * KiB)
    repository = Repository(REPO_URL, cache)
    package_index = RepoPackageIndex(packages=[
        RepoPackageVersionsFactory().build(**package_versions)  # type: ignore[arg-type]
    ])

    with patch('questionpy_server.repository.download') as mock_download, \
            patch.object(cache, 'put', wraps=cache.put) as mock_put:
        parsed = dumps(package_index, default=semver_encoder)
        mock_download.return_value = compress(parsed.encode())

        # Get packages.
        meta: RepoMeta = RepoMetaFactory.build()
        index_1 = await repository.get_packages(meta)
        mock_put.assert_awaited_once_with(meta.sha256, ANY)

    with patch.object(cache, 'get', wraps=cache.get) as mock_get:
        # Get packages again.
        index_2 = await repository.get_packages(meta)
        mock_get.assert_called_once_with(meta.sha256)

    assert index_1 == index_2


async def test_get_package() -> None:
    repository = Repository(REPO_URL, Mock())

    manifest = ManifestFactory.build(short_name='package', namespace='namespace')
    package_path = 'path/to/package.qpy'
    package = RepoPackage(manifest=manifest, sha256='hash', size=1, path=package_path)

    with patch('questionpy_server.repository.download') as mock:
        mock.return_value = b'package'

        # Get package.
        data = await repository.get_package(package)

        # Check if correct url gets called.
        url = urljoin(REPO_URL, str(package_path))
        mock.assert_called_once_with(url, size=package.size, expected_hash=package.sha256)

        assert data == b'package'
