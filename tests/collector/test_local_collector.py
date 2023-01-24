from asyncio import get_running_loop, sleep, wait_for
from pathlib import Path
from shutil import copy
from typing import Callable
from unittest.mock import patch

import asyncio
import pytest
from _pytest.tmpdir import TempPathFactory

from questionpy_server.package import Package
from questionpy_server.worker.controller import WorkerPool
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.local_collector import LocalCollector
from tests.conftest import PACKAGE, PACKAGE_2, get_file_hash


def create_local_collector(tmp_path_factory: TempPathFactory) -> tuple[LocalCollector, Path]:
    """
    Create a local collector and return it and the directory it is using.

    :param tmp_path_factory: Factory for temporary directories.
    :return: Local collector and directory.
    """

    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(1, 200 * 1024 * 1024))
    return LocalCollector(path, indexer), path


class WaitForAsyncFunctionCall:
    def __init__(self, func: Callable):
        """
        Wrapper around a function that is being watched.

        :param func: Function to wait for.
        """
        self.func = func
        self.fut = get_running_loop().create_future()

    async def wrap(self, *args: Any, **kwargs: Any) -> Any:
        """Method to pass as side_effect to patch(.object)."""
        try:
            ret = await self.func(*args, **kwargs)
            self.fut.set_result(True)
            return ret
        except Exception as e:  # pylint: disable=broad-except
            self.fut.set_exception(e)

    async def wait_for_fn_call(self, timeout: float) -> None:
        """
        Wait until the function has been called.

        :param timeout: Maximum time to wait (in seconds).
        """
        try:
            await wait_for(self.fut, timeout)
        except asyncio.TimeoutError:
            pytest.fail(f"Function {self.func} has not been called within {timeout} seconds.", False)


async def test_ignore_files_with_wrong_extension(tmp_path_factory: TempPathFactory) -> None:
    # File exists before initializing.
    directory = tmp_path_factory.mktemp('qpy')
    ignore_file = directory / 'wrong.extension'
    ignore_file.touch()

    indexer = Indexer(WorkerPool(1, 200 * 1024 * 1024))
    local_collector = LocalCollector(directory, indexer)

    async with local_collector:
        assert len(local_collector.map.paths) == 0

    # File gets created after initialization.
    local_collector, directory = create_local_collector(tmp_path_factory)
    async with local_collector:
        ignore_file = directory / 'wrong.extension'
        ignore_file.touch()
        assert len(local_collector.map.paths) == 0


async def test_package_exists_before_init(tmp_path_factory: TempPathFactory) -> None:
    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(1, 200 * 1024 * 1024))
    local_collector = LocalCollector(path, indexer)

    package_path = copy(PACKAGE.path, path)
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        # Package should exist.
        actual_package_path = await local_collector.get_path(package)
        assert actual_package_path.is_file()
        assert str(actual_package_path) == package_path
        assert get_file_hash(actual_package_path) == package.hash


async def test_package_gets_created(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    async with local_collector:
        register = WaitForAsyncFunctionCall(local_collector.indexer.register_package)
        with patch.object(local_collector.indexer, 'register_package', side_effect=register.wrap) as mock_register:

            # Copy a package to the directory.
            package_path = Path(copy(PACKAGE.path, directory))
            package = Package(PACKAGE.hash, PACKAGE.manifest)

            await register.wait_for_fn_call(10)

            # Package got registered in the indexer and local collector.
            mock_register.assert_awaited_with(package.hash, package_path, local_collector)
            assert package_path == await local_collector.get_path(package)


async def test_package_gets_modified(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    package_path = Path(copy(PACKAGE.path, directory))
    package_0 = Package(PACKAGE.hash, PACKAGE.manifest)
    package_1 = Package(PACKAGE_2.hash, PACKAGE_2.manifest)

    async with local_collector:
        register = WaitForAsyncFunctionCall(local_collector.indexer.register_package)
        unregister = WaitForAsyncFunctionCall(local_collector.indexer.unregister_package)
        with patch.object(local_collector.indexer, 'register_package', side_effect=register.wrap) as mock_register, \
             patch.object(local_collector.indexer, 'unregister_package',
                          side_effect=unregister.wrap) as mock_unregister:

            # Modify the package.
            package_path.write_bytes(PACKAGE_2.path.read_bytes())
            await register.wait_for_fn_call(10)
            await unregister.wait_for_fn_call(10)

            # Old package got unregistered and the new one registered in the indexer and local collector.
            mock_register.assert_awaited_with(package_1.hash, package_path, local_collector)
            mock_unregister.assert_awaited_with(package_0.hash, local_collector)

            with pytest.raises(FileNotFoundError):
                await local_collector.get_path(package_0)
            assert Path(package_path) == await local_collector.get_path(package_1)


async def test_package_gets_deleted(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    package_path = Path(copy(PACKAGE.path, directory))
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        unregister = WaitForAsyncFunctionCall(local_collector.indexer.unregister_package)
        with patch.object(local_collector.indexer, 'unregister_package',
                          side_effect=unregister.wrap) as mock_unregister:
            # Remove package from the directory.
            package_path.unlink()
            await unregister.wait_for_fn_call(10)

            # Package got unregistered in the indexer and local collector.
            mock_unregister.assert_awaited_with(package.hash, local_collector)
            with pytest.raises(FileNotFoundError):
                await local_collector.get_path(package)


async def test_package_gets_moved_from_package_to_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = Path(copy(PACKAGE.path, directory))
    dest_path = src_path.with_suffix('.renamed.qpy')
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'register_package') as mock_register, \
             patch.object(local_collector.indexer, 'unregister_package') as mock_unregister:

            # Rename the package.
            src_path.rename(dest_path)
            await sleep(0.5)

            # Package should neither get registered in nor unregistered from the indexer.
            mock_register.assert_not_awaited()
            mock_unregister.assert_not_awaited()

            # Old filename got replaced in local collector.
            assert dest_path == await local_collector.get_path(package)


async def test_package_gets_moved_from_non_package_to_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = Path(copy(PACKAGE.path, directory / 'non.package'))
    dest_path = src_path.with_suffix('.qpy')
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        register = WaitForAsyncFunctionCall(local_collector.indexer.register_package)
        with patch.object(local_collector.indexer, 'register_package', side_effect=register.wrap) as mock_register:
            # Rename the package.
            src_path.rename(dest_path)
            await register.wait_for_fn_call(10)

            # Package got registered in the indexer and local collector.
            mock_register.assert_awaited_with(package.hash, dest_path, local_collector)
            assert dest_path == await local_collector.get_path(package)


async def test_package_gets_moved_from_package_to_non_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = Path(copy(PACKAGE.path, directory))
    dest_path = src_path.with_suffix('.notqpy')
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        unregister = WaitForAsyncFunctionCall(local_collector.indexer.unregister_package)
        with patch.object(local_collector.indexer, 'unregister_package',
                          side_effect=unregister.wrap) as mock_unregister:
            # Rename the package.
            Path(src_path).rename(dest_path)
            await unregister.wait_for_fn_call(10)

            # Package got unregistered in the indexer and local collector.
            mock_unregister.assert_awaited_with(package.hash, local_collector)
            with pytest.raises(FileNotFoundError):
                await local_collector.get_path(package)


@pytest.mark.parametrize('inside', [
    True,
    False
])
async def test_package_gets_moved_to_different_folder(tmp_path_factory: TempPathFactory, inside: bool) -> None:
    # Create directories.
    directory = tmp_path_factory.mktemp('qpy')
    new_directory = directory / 'new'
    new_directory.mkdir()

    if not inside:
        # Use new_directory as the directory to be watched and directory to be the new directory of the package.
        directory, new_directory = new_directory, directory

    indexer = Indexer(WorkerPool(1, 200 * 1024 * 1024))
    local_collector = LocalCollector(directory, indexer)

    # Create a package in the directory.
    src_path = Path(copy(PACKAGE.path, directory))
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        unregister = WaitForAsyncFunctionCall(local_collector.indexer.unregister_package)
        with patch.object(local_collector.indexer, 'unregister_package',
                          side_effect=unregister.wrap) as mock_unregister:
            # Move the package.
            src_path.rename(new_directory / src_path.name)
            await unregister.wait_for_fn_call(10)

            # Package got unregistered in the indexer and local collector.
            mock_unregister.assert_awaited_with(package.hash, local_collector)
            with pytest.raises(FileNotFoundError):
                await local_collector.get_path(package)
