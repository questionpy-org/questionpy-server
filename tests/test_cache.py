# pylint: disable=redefined-outer-name, protected-access

from dataclasses import dataclass
from pathlib import Path
from string import ascii_lowercase
from typing import NamedTuple, List, Tuple
from unittest.mock import patch

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server.cache import FileLimitLRU, SizeError


@dataclass
class ItemSettings:
    size_per_item: int
    num_of_items: int

    def __post_init__(self) -> None:
        self.list = [(char, self.size_per_item * char.encode()) for char in ascii_lowercase[:self.num_of_items]]
        self.total_size = self.size_per_item * self.num_of_items


class CacheSettings(NamedTuple):
    size: int
    directory: Path


class Settings(NamedTuple):
    cache: CacheSettings
    items: ItemSettings


@pytest.fixture
def settings(tmp_path_factory: TempPathFactory) -> Settings:
    return Settings(
        cache=CacheSettings(
            size=100,
            directory=tmp_path_factory.mktemp('qpy'),
        ),
        items=ItemSettings(
            size_per_item=15,
            num_of_items=6
        )
    )


def write_files_to_directory(files: List[Tuple[str, bytes]], directory: Path) -> None:
    """
    Writes files onto a specific directory on the filesystem.

    :param files: files to be written
    :param directory: where files should be created
    """

    for file, content in files:
        file_path = directory / file
        file_path.write_bytes(content)


def get_file_count(directory: Path) -> int:
    """
    Counts files in a directory.

    :param directory: of which to get the file count
    :return: count of files in directory
    """

    return len(list(file for file in directory.iterdir() if file.is_file()))


def get_directory_size(directory: str) -> int:
    """
    Calculates directory size.

    :param directory: of which to get the size
    :return: size of directory
    """

    return sum(file.stat().st_size for file in Path(directory).iterdir() if file.is_file())


@pytest.fixture
def path_with_too_many_bytes(tmp_path_factory: TempPathFactory, settings: Settings) -> Path:
    directory = tmp_path_factory.mktemp('qpy')
    write_files_to_directory(settings.items.list, directory)

    large_item_path = directory / 'large_item'
    large_item_path.write_bytes(b'.' * (settings.cache.size - settings.items.total_size + 1))

    return directory


@pytest.fixture
def cache(settings: Settings) -> FileLimitLRU:
    write_files_to_directory(settings.items.list, Path(settings.cache.directory))
    return FileLimitLRU(settings.cache.directory, settings.cache.size)


def test_init(cache: FileLimitLRU, settings: Settings, path_with_too_many_bytes: Path) -> None:
    assert cache.total_size == settings.items.total_size
    assert cache.space_left == settings.cache.size - settings.items.total_size
    assert get_file_count(settings.cache.directory) == settings.items.num_of_items

    # Existing path contains more bytes than the cache can hold.
    small_cache = FileLimitLRU(path_with_too_many_bytes, settings.cache.size)
    assert small_cache.total_size <= settings.cache.size
    assert get_directory_size(str(path_with_too_many_bytes)) <= settings.cache.size

    # Ignore directories.
    (Path(settings.cache.directory) / "test_dir").mkdir()
    FileLimitLRU(settings.cache.directory, settings.cache.size)

    # Remove files with temporary extension.
    tmp_file = Path(settings.cache.directory) / ("file.txt" + cache._tmp_extension)
    tmp_file.write_bytes(b'.')
    new_cache = FileLimitLRU(settings.cache.directory, settings.cache.size)
    assert not tmp_file.is_file()
    assert get_file_count(settings.cache.directory) == settings.items.num_of_items
    assert new_cache.total_size == settings.items.total_size


async def test_remove(cache: FileLimitLRU, settings: Settings) -> None:
    # Remove a file.
    file, _ = settings.items.list[0]
    await cache.remove(file)
    assert not (cache.directory / file).is_file()
    expected_total_size = settings.items.total_size - settings.items.size_per_item
    assert cache.total_size == expected_total_size

    # Removing a file should fire the callback.
    with patch.object(cache, 'on_remove') as mock:
        file, _ = settings.items.list[-1]
        await cache.remove(file)
        expected_total_size = settings.items.total_size - 2 * settings.items.size_per_item
        assert not (cache.directory / file).is_file()
        assert cache.total_size == expected_total_size
        mock.assert_called_once()

    # Remove previously removed file.
    with pytest.raises(FileNotFoundError):
        await cache.remove(file)
    assert cache.total_size == expected_total_size

    # Remove not existing file.
    with pytest.raises(FileNotFoundError):
        await cache.remove('doesnotexist')
    assert cache.total_size == expected_total_size


def test_get(cache: FileLimitLRU, settings: Settings) -> None:
    # Get first added item.
    file, content = settings.items.list[0]
    path = cache.get(file)
    assert path == Path(settings.cache.directory) / file
    assert path.read_bytes() == content

    # Get last added item.
    file, content = settings.items.list[-1]
    path = cache.get(file)
    assert path == Path(settings.cache.directory) / file
    assert path.read_bytes() == content

    # Get not existing item.
    with pytest.raises(FileNotFoundError):
        cache.get('doesnotexist')


def test_contains(cache: FileLimitLRU, settings: Settings) -> None:
    # Check first added file.
    file, _ = settings.items.list[0]
    assert cache.contains(file)

    # Check last added file.
    file, _ = settings.items.list[-1]
    assert cache.contains(file)

    # Check not existing file.
    assert not cache.contains('doesnotexist')


async def test_put(cache: FileLimitLRU, settings: Settings) -> None:
    # Content type is not bytes.
    with pytest.raises(TypeError):
        await cache.put('new', 'string')  # type: ignore[arg-type]
    assert cache.total_size == settings.items.total_size
    assert get_file_count(settings.cache.directory) == settings.items.num_of_items

    # Content size is bigger than cache size.
    with pytest.raises(SizeError):
        await cache.put('new', b'.' * (settings.cache.size + 1))

    # Replace existing file.
    file, _ = settings.items.list[0]
    new_content = b'.' * settings.items.size_per_item
    await cache.put(file, new_content)
    assert (Path(settings.cache.directory) / file).read_bytes() == new_content
    assert cache.total_size == settings.items.total_size

    # Put max sized content into cache.
    file, content = 'A', b'.' * settings.cache.size
    await cache.put(file, content)
    assert (Path(settings.cache.directory) / file).is_file()
    assert cache.total_size == settings.cache.size
    assert get_file_count(settings.cache.directory) == 1

    # Partially written file raises error.
    with patch('questionpy_server.cache.Path.write_bytes', return_value=-1):
        with pytest.raises(IOError):
            await cache.put('B', b'.')

    # Delete every file in directory.
    for filepath in Path(settings.cache.directory).iterdir():
        filepath.unlink()

    # Remove the oldest file in cache.
    filecount = 3
    datasize = settings.cache.size // filecount
    files, content = [str(i) for i in range(filecount)], b'.' * datasize

    for file in files:
        await cache.put(file, content)

    for i in range(filecount):
        # Add new file to cache and check if the oldest file is removed.
        new_file = str(filecount + i + 1)
        await cache.put(new_file, content)

        assert cache.total_size == datasize * filecount
        assert cache.total_size <= settings.cache.size
        assert get_file_count(settings.cache.directory) == filecount
        assert (Path(settings.cache.directory) / new_file).is_file()
        assert not (Path(settings.cache.directory) / files[i]).is_file()


def test_get_files(cache: FileLimitLRU, settings: Settings) -> None:
    # Check if cache.file is only a copy of the original dict.
    assert cache.files == cache._files
    assert cache.files is not cache._files
    assert len(cache.files) == settings.items.num_of_items
