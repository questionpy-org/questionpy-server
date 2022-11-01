from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector import PackageCollector


@dataclass
class Settings:
    files_per_location: int

    cache_dir: Path
    local_dir: Path

    def __post_init__(self) -> None:

        def create_files(directory: Path, files: List[str]) -> None:
            for file in files:
                file_path = directory / (file + '.qpy')
                file_path.write_bytes(b'.')

        self.cache_files: List[str] = [str(i) for i in range(self.files_per_location)]
        self.local_files = [str(i) for i in range(self.files_per_location, 2 * self.files_per_location + 1)]

        create_files(self.cache_dir, self.cache_files)
        create_files(self.local_dir, self.local_files)


def create_collector(local_dir: Path, cache_dir: Path) -> PackageCollector:

    return PackageCollector(
        local_dir=str(local_dir),
        cache=FileLimitLRU(
            directory=cache_dir,
            max_bytes=10,
            extension='.qpy',
        ))


@pytest.fixture
def settings(tmp_path_factory: TempPathFactory) -> Settings:
    return Settings(
        files_per_location=6,
        local_dir=tmp_path_factory.mktemp('qpy'),
        cache_dir=tmp_path_factory.mktemp('qpy'),
    )


def test_init(tmp_path_factory: TempPathFactory) -> None:
    # Test PackageCollector initialization without local directory.
    PackageCollector(None, FileLimitLRU(tmp_path_factory.mktemp('qpy'), 1))


def test_contains(settings: Settings) -> None:
    collector = create_collector(settings.local_dir, settings.cache_dir)

    assert collector.contains(settings.local_files[0])
    assert collector.contains(settings.cache_files[0])
    assert not collector.contains('A')

    # Without local directory.
    collector._local_dir = None
    assert collector.contains(settings.cache_files[0])
    assert not collector.contains(settings.local_files[0])


def test_get(settings: Settings) -> None:
    collector = create_collector(settings.local_dir, settings.cache_dir)

    # Get local file.
    expected_local_path = settings.local_dir / (settings.local_files[0] + '.qpy')
    assert expected_local_path.is_file()
    assert expected_local_path == collector.get(settings.local_files[0])

    # Get cached file.
    expected_cache_path = settings.cache_dir / (settings.cache_files[0] + '.qpy')
    assert expected_cache_path.is_file()
    assert expected_cache_path == collector.get(settings.cache_files[0])

    # Get not existing file.
    with pytest.raises(FileNotFoundError):
        collector.get('A')

    # Without local directory.
    collector._local_dir = None

    expected_cache_path = settings.cache_dir / (settings.cache_files[0] + '.qpy')
    assert expected_cache_path.is_file()
    assert expected_cache_path == collector.get(settings.cache_files[0])

    with pytest.raises(FileNotFoundError):
        collector.get(settings.local_files[0])
