from pathlib import Path
from shutil import copy
from typing import NamedTuple

import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server import WorkerPool
from questionpy_server.cache import FileLimitLRU
from questionpy_server.collector import PackageCollector
from questionpy_server.collector.collector import LocalCollector
from questionpy_server.web import HashContainer
from tests.conftest import PACKAGES


def create_collector(local_dir: Path, cache_dir: Path) -> PackageCollector:
    return PackageCollector(
        local_dir=local_dir,
        repo_urls=[],
        worker_pool=WorkerPool(0, 0),
        cache=FileLimitLRU(
            directory=cache_dir,
            max_bytes=40000,
            extension='.qpy',
        ))


class Settings(NamedTuple):
    cache_dir: Path
    local_dir: Path


@pytest.fixture
def settings(tmp_path_factory: TempPathFactory) -> Settings:
    return Settings(
        local_dir=tmp_path_factory.mktemp('qpy'),
        cache_dir=tmp_path_factory.mktemp('qpy'),
    )


def test_init(tmp_path_factory: TempPathFactory) -> None:
    # Test PackageCollector initialization without local directory.
    PackageCollector(None, [], FileLimitLRU(directory=tmp_path_factory.mktemp('qpy'), max_bytes=1),
                     WorkerPool(0, 0))

    # Test PackageCollector initializes every sub-collector.
    collector = PackageCollector(tmp_path_factory.mktemp('qpy'), ['www.example.com/1', 'www.example.com/2'],
                                 FileLimitLRU(directory=tmp_path_factory.mktemp('qpy'), max_bytes=1),
                                 WorkerPool(0, 0))
    assert len(collector._collectors) == 3


async def test_with_only_local_packages(settings: Settings) -> None:
    # Ignore files not ending with .qpy.
    (settings.local_dir / 'not-a-package').touch()

    copy(PACKAGES[0].path, settings.local_dir)
    collector = create_collector(settings.local_dir, settings.cache_dir)

    # Get local package by hash.
    await collector.get(PACKAGES[0].hash)

    # Get local package by collecting all available packages.
    packages = await collector.get_packages()
    assert len(packages) == 1

    package_1 = packages.pop()
    assert package_1.hash == PACKAGES[0].hash

    # Get local package by name.
    packages_and_version = await collector.get_by_name(package_1.manifest.short_name)
    assert len(packages_and_version) == 1
    assert package_1 == packages_and_version.pop(package_1.manifest.version)

    # Get local package by name and version.
    package_2 = await collector.get_by_name_and_version(package_1.manifest.short_name, package_1.manifest.version)
    assert package_1 == package_2

    # Not available package should raise FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        await collector.get('doesnotexist')


async def test_with_only_lms_packages(settings: Settings) -> None:
    collector = create_collector(settings.local_dir, settings.cache_dir)

    # Test put new package into collector.
    package_container = HashContainer(PACKAGES[0].path.read_bytes(), PACKAGES[0].hash)
    package = await collector.put(package_container)

    # Test getting package by hash.
    assert package == await collector.get(PACKAGES[0].hash)

    # Package should not be listed in get_packages().
    packages = await collector.get_packages()
    assert len(packages) == 0

    # Package should not be accessible via name.
    packages_and_version = await collector.get_by_name(package.manifest.short_name)
    assert 0 == len(packages_and_version)

    # Package should not be accessible via short name and version.
    with pytest.raises(FileNotFoundError):
        await collector.get_by_name_and_version(package.manifest.short_name, package.manifest.version)


async def test_with_local_and_lms_packages(settings: Settings) -> None:
    # Put same package into local and LMS collector.
    copy(PACKAGES[0].path, settings.local_dir)
    collector = create_collector(settings.local_dir, settings.cache_dir)

    package_container = HashContainer(PACKAGES[0].path.read_bytes(), PACKAGES[0].hash)
    package = await collector.put(package_container)

    # Check if lms collector did not overwrite local package since it already existed.
    assert len(await collector.get_packages()) == 1
    assert isinstance(package._collector, LocalCollector)
