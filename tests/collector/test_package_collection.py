from pathlib import Path
from unittest.mock import patch, Mock

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector import PackageCollection
from questionpy_server.web import HashContainer

from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.collector.lms_collector import LMSCollector


async def test_start() -> None:
    package_collection = PackageCollection(Path("test_dir/"), [], Mock(), Mock())

    with patch.object(LMSCollector, 'start') as lms_start, patch.object(LocalCollector, 'start') as local_start:
        await package_collection.start()
        lms_start.assert_called_once()
        local_start.assert_called_once()


async def test_stop() -> None:
    package_collection = PackageCollection(Path("test_dir/"), [], Mock(), Mock())

    with patch.object(LMSCollector, 'stop') as lms_stop, patch.object(LocalCollector, 'stop') as local_stop:
        await package_collection.stop()
        lms_stop.assert_called_once()
        local_stop.assert_called_once()


async def test_put_package() -> None:
    package_collection = PackageCollection(None, [], Mock(), Mock())

    with patch.object(LMSCollector, 'put') as put:
        await package_collection.put(HashContainer(b'', 'hash'))
        put.assert_called_once_with(HashContainer(b'', 'hash'))


def test_get_package() -> None:
    package_collection = PackageCollection(None, [], Mock(), Mock())

    # Package does exist.
    with patch('questionpy_server.collector.indexer.Indexer.get_by_hash') as get_by_hash:
        package_collection.get('hash')
        get_by_hash.assert_called_once_with('hash')

    # Package does not exist.
    with patch('questionpy_server.collector.indexer.Indexer.get_by_hash', return_value=None) as get_by_hash:
        with pytest.raises(FileNotFoundError):
            package_collection.get('hash')
        get_by_hash.assert_called_once_with('hash')


def test_get_package_by_name() -> None:
    package_collection = PackageCollection(None, [], Mock(), Mock())

    with patch('questionpy_server.collector.indexer.Indexer.get_by_name') as get_by_name:
        package_collection.get_by_name('hash')
        get_by_name.assert_called_once_with('hash')


def test_get_package_by_name_and_version() -> None:
    package_collection = PackageCollection(None, [], Mock(), Mock())

    # Package does exist.
    with patch('questionpy_server.collector.indexer.Indexer.get_by_name_and_version') as get_by_name_and_version:
        package_collection.get_by_name_and_version('hash', '0.1.0')
        get_by_name_and_version.assert_called_once_with('hash', '0.1.0')

    # Package does not exist.
    with patch('questionpy_server.collector.indexer.Indexer.get_by_name_and_version', return_value=None) as \
            get_by_name_and_version:
        with pytest.raises(FileNotFoundError):
            package_collection.get_by_name_and_version('hash', '0.1.0')
        get_by_name_and_version.assert_called_once_with('hash', '0.1.0')


def test_get_packages() -> None:
    package_collection = PackageCollection(None, [], Mock(), Mock())

    # Package does exist.
    with patch('questionpy_server.collector.indexer.Indexer.get_packages') as get_packages:
        package_collection.get_packages()
        get_packages.assert_called_once()


async def test_notify_indexer_on_cache_deletion(tmp_path_factory: TempPathFactory) -> None:
    cache = FileLimitLRU(tmp_path_factory.mktemp('qpy'), 100)
    PackageCollection(None, [], cache, Mock())

    # The callback should unregister the package from the indexer.
    with patch('questionpy_server.collector.indexer.Indexer.unregister_package') as unregister_package:
        cache.on_remove('hash')
        unregister_package.assert_called_once()
