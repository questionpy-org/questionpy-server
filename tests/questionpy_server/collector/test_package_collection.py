#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from pathlib import Path
from unittest.mock import Mock, patch

from _pytest.tmpdir import TempPathFactory
from semver import VersionInfo

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector import PackageCollection
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.lms_collector import LMSCollector
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.web import HashContainer


async def test_start() -> None:
    package_collection = PackageCollection(Path("test_dir/"), {}, Mock(), Mock(), Mock())

    with patch.object(LMSCollector, "start") as lms_start, patch.object(LocalCollector, "start") as local_start:
        await package_collection.start()
        lms_start.assert_called_once()
        local_start.assert_called_once()


async def test_stop() -> None:
    package_collection = PackageCollection(Path("test_dir/"), {}, Mock(), Mock(), Mock())

    with patch.object(LMSCollector, "stop") as lms_stop, patch.object(LocalCollector, "stop") as local_stop:
        await package_collection.stop()
        lms_stop.assert_called_once()
        local_stop.assert_called_once()


async def test_put_package() -> None:
    package_collection = PackageCollection(None, {}, Mock(), Mock(), Mock())

    with patch.object(LMSCollector, "put") as put:
        await package_collection.put(HashContainer(b"", "hash"))
        put.assert_called_once_with(HashContainer(b"", "hash"))


def test_get_package() -> None:
    package_collection = PackageCollection(None, {}, Mock(), Mock(), Mock())

    # Package does exist.
    with patch.object(Indexer, "get_by_hash") as get_by_hash:
        package_collection.get("hash")
        get_by_hash.assert_called_once_with("hash")

    # Package does not exist.
    with patch.object(Indexer, "get_by_hash", return_value=None) as get_by_hash:
        assert package_collection.get("hash") is None
        get_by_hash.assert_called_once_with("hash")


def test_get_package_by_identifier() -> None:
    package_collection = PackageCollection(None, {}, Mock(), Mock(), Mock())

    with patch.object(Indexer, "get_by_identifier") as get_by_identifier:
        package_collection.get_by_identifier("@default/name")
        get_by_identifier.assert_called_once_with("@default/name")


def test_get_package_by_identifier_and_version() -> None:
    package_collection = PackageCollection(None, {}, Mock(), Mock(), Mock())

    # Package does exist.
    with patch.object(Indexer, "get_by_identifier_and_version") as get_by_identifier_and_version:
        version = VersionInfo.parse("0.1.0")
        package_collection.get_by_identifier_and_version("@default/name", version)
        get_by_identifier_and_version.assert_called_once_with("@default/name", version)

    # Package does not exist.
    with patch.object(Indexer, "get_by_identifier_and_version", return_value=None) as get_by_identifier_and_version:
        version = VersionInfo.parse("0.1.0")
        assert package_collection.get_by_identifier_and_version("@default/name", version) is None
        get_by_identifier_and_version.assert_called_once_with("@default/name", version)


def test_get_packages() -> None:
    package_collection = PackageCollection(None, {}, Mock(), Mock(), Mock())

    # Package does exist.
    with patch.object(Indexer, "get_package_versions_infos") as get_package_versions_infos:
        package_collection.get_package_versions_infos()
        get_package_versions_infos.assert_called_once()


async def test_notify_indexer_on_cache_deletion(tmp_path_factory: TempPathFactory) -> None:
    cache = FileLimitLRU(tmp_path_factory.mktemp("qpy"), 100)
    PackageCollection(None, {}, Mock(), cache, Mock())

    # The callback should unregister the package from the indexer.
    with patch.object(Indexer, "unregister_package") as unregister_package:
        await cache.on_remove("hash")
        unregister_package.assert_called_once()
