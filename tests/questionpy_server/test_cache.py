#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server.cache import CacheItemTooLargeError, LRUCache, LRUCacheSupervisor


def get_file_count(directory: Path) -> int:
    """Counts files in a directory."""
    return len([file for file in directory.iterdir() if file.is_file()])


def get_directory_size(directory: Path) -> int:
    """Calculates directory size."""
    return sum(file.stat().st_size for file in directory.iterdir() if file.is_file())


def write_data(to: Path, amount: int) -> None:
    to.parent.mkdir(exist_ok=True)
    to.write_bytes(b"." * amount)


def test_init_removes_files_if_cache_is_full(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 2)

    cache_subdirectory = Path("cache")
    cache_path = supervisor.directory / cache_subdirectory

    write_data(cache_path / "A", 1)
    write_data(cache_path / "B", 2)

    cache = LRUCache(supervisor, cache_subdirectory)

    assert get_file_count(cache_path) == 1
    assert get_directory_size(cache.directory) == supervisor.total_size
    assert 0 < supervisor.total_size <= 2
    assert {True, False} == {cache.contains("A"), cache.contains("B")}


def test_supervisor_creates_cache_directory_in_supervisor_directory(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)

    cache_subdirectory = Path("cache")
    cache = LRUCache(supervisor, cache_subdirectory)

    assert cache.directory == supervisor.directory / cache_subdirectory
    assert cache.directory.is_dir()


def test_init_removes_files_with_temporary_extension(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)

    cache_subdirectory = Path("cache")

    file_path = supervisor.directory / cache_subdirectory / "A.tmp"
    write_data(file_path, 1)

    LRUCache(supervisor, cache_subdirectory)

    assert not file_path.is_file()
    assert supervisor.total_size == 0


async def test_put_with_multiple_caches(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 2)

    cache_1_subdirectory = Path("cache_1")
    cache_2_subdirectory = Path("cache_2")

    cache_1 = LRUCache(supervisor, cache_1_subdirectory)
    cache_2 = LRUCache(supervisor, cache_2_subdirectory)

    await cache_1.put("A", b"A")
    await cache_2.put("B", b"B")

    assert cache_1.contains("A")
    assert not cache_1.contains("B")
    assert cache_1.files.keys() == {"A"}
    assert (supervisor.directory / cache_1_subdirectory / "A").is_file()

    assert cache_2.contains("B")
    assert not cache_2.contains("A")
    assert cache_2.files.keys() == {"B"}
    assert (supervisor.directory / cache_2_subdirectory / "B").is_file()

    assert supervisor.total_size == 2


async def test_put_with_data_bigger_than_capacity_raises(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)

    cache_subdirectory = Path("cache")
    cache = LRUCache(supervisor, cache_subdirectory)

    with pytest.raises(CacheItemTooLargeError):
        await cache.put("A", b"..")

    assert not cache.contains("A")
    assert supervisor.total_size == 0
    assert not (supervisor.directory / cache_subdirectory / "A").is_file()


async def test_put_raises_if_written_bytes_does_not_match_expected_size(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)

    cache_subdirectory = Path("cache")
    cache = LRUCache(supervisor, cache_subdirectory)

    with (
        patch("pathlib.Path.write_bytes", return_value=-1),
        pytest.raises(IOError, match="Failed to write bytes"),
    ):
        await cache.put("B", b".")


async def test_put_removes_lru_file_if_cache_is_full(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)

    cache_1_subdirectory = Path("cache_1")
    cache_2_subdirectory = Path("cache_2")

    cache_1 = LRUCache(supervisor, cache_1_subdirectory)
    cache_2 = LRUCache(supervisor, cache_2_subdirectory)

    await cache_1.put("A", b"A")
    await cache_2.put("B", b"B")

    assert not cache_1.contains("A")
    assert not (supervisor.directory / cache_1_subdirectory / "A").is_file()

    assert cache_2.contains("B")
    assert (supervisor.directory / cache_2_subdirectory / "B").is_file()

    assert supervisor.total_size == 1


async def test_remove_raises_if_file_does_not_exist(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)
    cache = LRUCache(supervisor, Path("cache"))
    with pytest.raises(FileNotFoundError):
        await cache.remove("doesnotexist")


async def test_remove_fires_callback_if_file_is_removed(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 2)

    cache_1 = LRUCache(supervisor, Path("cache_1"))
    cache_2 = LRUCache(supervisor, Path("cache_2"))

    cache_1_callback = AsyncMock()
    cache_2_callback = AsyncMock()

    cache_1.set_on_remove_callback(cache_1_callback)
    cache_2.set_on_remove_callback(cache_2_callback)

    await cache_1.put("A", b"A")
    await cache_2.put("B", b"B")

    # LRU file will be removed.
    await cache_1.put("C", b"C")
    cache_1_callback.assert_called_once_with("A")
    cache_2_callback.assert_not_called()

    await cache_2.remove("B")
    cache_2_callback.assert_called_once_with("B")
    cache_1_callback.assert_called_once()


async def test_cache_with_file_extension(tmp_path_factory: TempPathFactory) -> None:
    supervisor = LRUCacheSupervisor(tmp_path_factory.mktemp("supervisor"), 1)
    cache = LRUCache(supervisor, Path("cache"), extension=".qpy")

    callback = AsyncMock()
    cache.set_on_remove_callback(callback)

    key = "A"
    expected_path = supervisor.directory / "cache" / f"{key}.qpy"

    await cache.put(key, b".")
    assert cache.contains(key)
    assert expected_path.is_file()
    assert cache.get(key) == expected_path
    assert cache.files.keys() == {key}

    await cache.remove(key)
    callback.assert_called_once_with(key)
    assert not cache.contains(key)
    assert not expected_path.is_file()
