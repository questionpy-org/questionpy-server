#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from asyncio import sleep
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from questionpy_server.collector.repo_collector import RepoCollector
from questionpy_server.repository.helper import DownloadError
from tests.test_data.factories import RepoMetaFactory


async def test_update_gets_called_periodically_after_start() -> None:
    collector = RepoCollector("", timedelta(seconds=0.1), AsyncMock(), AsyncMock(), AsyncMock())
    with patch.object(collector, "update") as update:
        async with collector:
            await sleep(0.25)
            assert update.call_count == 3  # 1 on startup + 2 during the test


async def test_update_downloads_packages_only_on_newer_package_index() -> None:
    collector = RepoCollector("", Mock(), AsyncMock(), AsyncMock(), AsyncMock())
    with patch.object(collector, "_repository") as repository:
        # Initial update.
        repository.get_packages = AsyncMock(return_value={})
        repository.get_meta = AsyncMock(return_value=RepoMetaFactory.build(timestamp=1))
        await collector.update()
        assert repository.get_packages.call_count == 1

        # No new package index.
        await collector.update()
        assert repository.get_packages.call_count == 1

        # Package index got updated.
        repository.get_meta = AsyncMock(return_value=RepoMetaFactory.build(timestamp=2))
        await collector.update()
        assert repository.get_packages.call_count == 2


@pytest.mark.parametrize(
    ("first_update", "second_update"),
    [
        ([], []),
        (["a"], []),
        ([], ["a"]),
        (["a", "b"], []),
        ([], ["a", "b"]),
        (["a", "b"], ["a"]),
        (["a", "b"], ["b"]),
        (["a", "b"], ["a", "b"]),
        (["a", "b"], ["c"]),
        (["a", "b"], ["a", "c"]),
        (["a", "b"], ["c", "d"]),
    ],
)
async def test_package_index_gets_updated(first_update: list[str], second_update: list[str]) -> None:
    indexer = AsyncMock()
    collector = RepoCollector("", Mock(), AsyncMock(), AsyncMock(), indexer)

    first_packages = {package_hash: Mock() for package_hash in first_update}
    second_packages = {package_hash: Mock() for package_hash in second_update}

    with patch.object(collector, "_repository") as repository:
        # Initial update.
        repository.get_packages = AsyncMock(return_value=first_packages)
        repository.get_meta = AsyncMock(return_value=RepoMetaFactory.build(timestamp=1))
        await collector.update()
        calls = [call(package_hash, package.manifest, collector) for package_hash, package in first_packages.items()]
        indexer.register_package.assert_has_calls(calls, any_order=True)

        # Update repository.
        repository.get_packages = AsyncMock(return_value=second_packages)
        repository.get_meta = AsyncMock(return_value=RepoMetaFactory.build(timestamp=2))
        await collector.update()

        # Removed packages should be unregistered.
        removed_package_hashes = first_packages.keys() - second_packages.keys()
        calls = [call(package_hash, collector) for package_hash in removed_package_hashes]
        indexer.unregister_package.assert_has_calls(calls, any_order=True)

        # Added packages should be registered.
        added_package_hashes = second_packages.keys() - first_packages.keys()
        calls = []
        for package_hash in added_package_hashes:
            calls.append(call(package_hash, second_packages[package_hash].manifest, collector))
        indexer.register_package.assert_has_calls(calls, any_order=True)


async def test_get_path_raises_file_not_found_error_if_package_does_not_exist() -> None:
    collector = RepoCollector("", Mock(), AsyncMock(), AsyncMock(), AsyncMock())
    with pytest.raises(FileNotFoundError):
        await collector.get_path(Mock())


async def test_get_path_raises_file_not_found_error_on_download_error() -> None:
    collector = RepoCollector("", Mock(), AsyncMock(), AsyncMock(), AsyncMock())

    package = Mock()

    with patch.object(collector, "_repository") as repository:
        # Initial update.
        repository.get_packages = AsyncMock(return_value={package.hash: package})
        repository.get_meta = AsyncMock(return_value=RepoMetaFactory.build(timestamp=1))
        await collector.update()

        # Get path.
        repository.get_package = AsyncMock(side_effect=DownloadError)
        with pytest.raises(FileNotFoundError):
            await collector.get_path(package)


async def test_get_path_caches_package() -> None:
    cache = AsyncMock()
    collector = RepoCollector("", Mock(), cache, AsyncMock(), AsyncMock())

    package = Mock()

    with patch.object(collector, "_repository") as repository:
        # Initial update.
        repository.get_packages = AsyncMock(return_value={package.hash: package})
        repository.get_meta = AsyncMock(return_value=RepoMetaFactory.build(timestamp=1))
        await collector.update()

        # Get path.
        repository.get_package = AsyncMock(return_value=b"data")
        await collector.get_path(package)
        repository.get_package.assert_called_once_with(package)
        cache.put.assert_called_once_with(package.hash, b"data")
