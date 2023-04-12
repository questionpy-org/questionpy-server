import asyncio
from asyncio import get_running_loop, wait_for
from os import kill, getpid
from pathlib import Path
from shutil import copy
from signal import SIGUSR1
from typing import Any, Callable
from unittest.mock import patch

import pytest
from _pytest.tmpdir import TempPathFactory
from questionpy_common.constants import MiB

from questionpy_server import WorkerPool
from questionpy_server.collector.indexer import Indexer
from questionpy_server.collector.local_collector import LocalCollector
from questionpy_server.package import Package
from tests.conftest import PACKAGE, PACKAGE_2, get_file_hash


def create_local_collector(tmp_path_factory: TempPathFactory) -> tuple[LocalCollector, Path]:
    """Create a local collector and return it and the directory it is using.

    Args:
        tmp_path_factory (TempPathFactory): Factory for temporary directories.

    Returns:
        Local collector and directory.
    """

    path = tmp_path_factory.mktemp('qpy')
    indexer = Indexer(WorkerPool(1, 200 * MiB))
    return LocalCollector(path, indexer), path


class WaitForAsyncFunctionCall:
    def __init__(self, func: Callable):
        """Wrapper around a function that is being watched.

        Args:
            func (Callable): Function to wait for.
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
        """Wait until the function has been called.

        Args:
            timeout (float): Maximum time to wait (in seconds).
        """
        try:
            await wait_for(self.fut, timeout)
        except asyncio.TimeoutError:
            pytest.fail(f"Function {self.func} has not been called within {timeout} seconds.", False)


async def test_run_update_on_signal(tmp_path_factory: TempPathFactory) -> None:
    local_collector, _ = create_local_collector(tmp_path_factory)

    async with local_collector:
        # Check that the update function is called on SIGUSR1.
        update = WaitForAsyncFunctionCall(local_collector.update)
        with patch.object(local_collector, 'update', side_effect=update.wrap) as mock_update:
            # Send signal.
            kill(getpid(), SIGUSR1)
            # Wait for signal handler to be called.
            await update.wait_for_fn_call(10)
            mock_update.assert_awaited_once()


async def test_ignore_files_with_wrong_extension(tmp_path_factory: TempPathFactory) -> None:
    # File exists before initializing.
    directory = tmp_path_factory.mktemp('qpy')
    ignore_file = directory / 'wrong.extension'
    ignore_file.touch()

    indexer = Indexer(WorkerPool(1, 200 * MiB))
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
    indexer = Indexer(WorkerPool(1, 200 * MiB))
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

    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'register_package') as mock_register:
            # Copy a package to the directory.
            package_path = Path(copy(PACKAGE.path, directory))
            await local_collector.update()

            # Package got registered in the indexer and local collector.
            mock_register.assert_awaited_once_with(package.hash, package_path, local_collector)
            assert package_path == await local_collector.get_path(package)


async def test_package_gets_modified(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    package_path = Path(copy(PACKAGE.path, directory))
    package_1 = Package(PACKAGE.hash, PACKAGE.manifest)
    package_2 = Package(PACKAGE_2.hash, PACKAGE_2.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'register_package') as mock_register, \
                patch.object(local_collector.indexer, 'unregister_package') as mock_unregister:
            # Modify the package.
            package_path.write_bytes(PACKAGE_2.path.read_bytes())
            await local_collector.update()

            # Old package got unregistered and the new one registered in the indexer and local collector.
            mock_register.assert_awaited_once_with(package_2.hash, package_path, local_collector)
            mock_unregister.assert_awaited_once_with(package_1.hash, local_collector)

            with pytest.raises(FileNotFoundError):
                await local_collector.get_path(package_1)
            assert Path(package_path) == await local_collector.get_path(package_2)


async def test_package_gets_deleted(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    package_path = Path(copy(PACKAGE.path, directory))
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'unregister_package') as mock_unregister:
            # Remove package from the directory.
            package_path.unlink()
            await local_collector.update()

            # Package got unregistered in the indexer and local collector.
            mock_unregister.assert_awaited_once_with(package.hash, local_collector)
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
            await local_collector.update()

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
        with patch.object(local_collector.indexer, 'register_package') as mock_register:
            # Rename the package.
            src_path.rename(dest_path)
            await local_collector.update()

            # Package got registered in the indexer and local collector.
            mock_register.assert_awaited_once_with(package.hash, dest_path, local_collector)
            assert dest_path == await local_collector.get_path(package)


async def test_package_gets_moved_from_package_to_non_package(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    # Create a package in the directory.
    src_path = Path(copy(PACKAGE.path, directory))
    dest_path = src_path.with_suffix('.notqpy')
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'unregister_package') as mock_unregister:
            # Rename the package.
            Path(src_path).rename(dest_path)
            await local_collector.update()

            # Package got unregistered in the indexer and local collector.
            mock_unregister.assert_awaited_once_with(package.hash, local_collector)
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

    indexer = Indexer(WorkerPool(1, 200 * MiB))
    local_collector = LocalCollector(directory, indexer)

    # Create a package in the directory.
    src_path = Path(copy(PACKAGE.path, directory))
    package = Package(PACKAGE.hash, PACKAGE.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'unregister_package') as mock_unregister:
            # Move the package.
            src_path.rename(new_directory / src_path.name)
            await local_collector.update()

            # Package got unregistered in the indexer and local collector.
            mock_unregister.assert_awaited_once_with(package.hash, local_collector)
            with pytest.raises(FileNotFoundError):
                await local_collector.get_path(package)


async def test_package_filenames_get_swapped(tmp_path_factory: TempPathFactory) -> None:
    local_collector, directory = create_local_collector(tmp_path_factory)

    package_1_path = Path(copy(PACKAGE.path, directory))
    package_1 = Package(PACKAGE.hash, PACKAGE.manifest)

    package_2_path = Path(copy(PACKAGE_2.path, directory))
    package_2 = Package(PACKAGE_2.hash, PACKAGE_2.manifest)

    async with local_collector:
        with patch.object(local_collector.indexer, 'register_package') as mock_register, \
                patch.object(local_collector.indexer, 'unregister_package') as mock_unregister:
            # Swap the package filenames.
            temporary_path = directory / 'temporary_path'
            package_1_path.rename(temporary_path)
            package_2_path.rename(package_1_path)
            temporary_path.rename(package_2_path)

            await local_collector.update()

            # The packages should be swapped in the local collector.
            assert package_2_path == await local_collector.get_path(package_1)
            assert package_1_path == await local_collector.get_path(package_2)

            # Packages should neither get registered in nor unregistered from the indexer.
            mock_register.assert_not_awaited()
            mock_unregister.assert_not_awaited()
