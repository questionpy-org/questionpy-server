#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import logging
from asyncio import Lock, to_thread
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from pydantic import ByteSize

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


_log = logging.getLogger(__name__)


class File(NamedTuple):
    path: Path
    size: int


type OnRemoveCallback = Callable[[str], Awaitable[None]]


class CacheItemTooLargeError(Exception):
    def __init__(self, key: str, actual_size: int, max_size: int):
        readable_actual = ByteSize(actual_size).human_readable()
        readable_max = ByteSize(max_size).human_readable()
        super().__init__(
            f"Unable to cache item '{key}' with size '{readable_actual}' because it exceeds the maximum "
            f"allowed size of '{readable_max}'"
        )

        self.max_size = max_size
        self.actual_size = actual_size


class LRUCacheSupervisor:
    """Supervises multiple file caches living in subdirectories of the given directory.

    It evicts the least recently accessed file when the specified maximum is exceeded.

    Only `bytes` type values are accepted. Their size is calculated by passing them into the builtin `len()`
    function.
    """

    def __init__(self, directory: Path, max_size: int) -> None:
        self.directory = directory
        self.max_size = max_size

        self._lock = Lock()
        self._tmp_extension = ".tmp"
        self._total_size: int = 0
        self._files: OrderedDict[Path, File] = OrderedDict()
        self._on_remove_callbacks: dict[Path, OnRemoveCallback] = {}

        _log.info("Initialized at '%s' with a maximum size of %s.", directory, ByteSize(max_size).human_readable())

    def set_on_remove_callback(self, subdirectory: Path, callback: OnRemoveCallback) -> None:
        self._on_remove_callbacks[subdirectory] = callback

    def register(self, subdirectory: Path) -> None:
        """Registers a subdirectory.

        Creates the subdirectory if it does not exist and removes containing files if the cache is too full and if
        they have the temporary file extension.
        """
        directory = self.directory / subdirectory
        directory.mkdir(exist_ok=True)

        for path in directory.iterdir():
            if not path.is_file():
                continue

            if path.suffix == self._tmp_extension:
                path.unlink(missing_ok=True)
                continue

            size = path.stat().st_size
            total = self._total_size + size

            # Remove files if cache is full.
            if total > self.max_size:
                path.unlink()
                continue

            self._total_size = total
            self._files[subdirectory / path.stem] = File(path, size)

    def contains(self, key: Path) -> bool:
        """Checks if the file exists in cache.

        Additionally, the file is placed to the end ensuring that it is the most recent accessed file.
        """
        if key not in self._files:
            return False

        self._files.move_to_end(key)
        return True

    def _get_file(self, key: Path) -> File:
        if not self.contains(key):
            raise FileNotFoundError

        return self._files[key]

    def get(self, key: Path) -> Path:
        """Returns path of the file in the cache.

        Raises:
            FileNotFoundError: If the file does not exist in the cache.
        """
        return self._get_file(key).path

    async def _remove(self, key: Path) -> None:
        file = self._get_file(key)
        await to_thread(file.path.unlink, missing_ok=True)
        self._total_size -= file.size
        del self._files[key]

        cache, real_key = key.parent, key.stem
        if cache in self._on_remove_callbacks:
            await self._on_remove_callbacks[cache](real_key)

    async def remove(self, key: Path) -> None:
        """Removes file from the cache and the filesystem."""
        async with self._lock:
            await self._remove(key)

    async def put(self, key: Path, value: bytes, extension: str) -> Path:
        """Puts a file in the cache and the filesystem.

        The internal `._total_bytes` attribute is updated.
        If the key existed before and just the value is replaced, the item is treated as most recently accessed and
        thus moved to the end of the internal linked list.
        If after adding the item `._total_bytes` exceeds `.max_bytes`, items are deleted in order from least to most
        recently accessed until the total size (in bytes) is in line with the specified maximum.

        Raises:
            TypeError: If `value` is not a `bytes` object.
            SizeError: If the length/size of the provided `value` exceeds `.max_bytes`.
        """
        if not isinstance(value, bytes):
            msg = "Not a bytes object:"
            raise TypeError(msg, repr(value))

        size = len(value)
        if size > self.max_size:
            # If we allowed this, the loop at the end would remove all items from the dictionary,
            # so we raise an error to allow exceptions for this case.
            raise CacheItemTooLargeError(key.stem, size, self.max_size)

        async with self._lock:
            # Save the bytes on filesystem.
            path = self.directory / (key.with_suffix(extension))
            tmp_path = path.parent / (path.name + self._tmp_extension)

            written_bytes = await to_thread(tmp_path.write_bytes, value)
            if size != written_bytes:
                tmp_path.unlink(missing_ok=True)
                _log.error(
                    "Failed to write all bytes (%s/%s) to file '%s'.",
                    ByteSize(written_bytes).human_readable(),
                    ByteSize(size).human_readable(),
                    tmp_path,
                )
                msg = "Failed to write bytes to file"
                raise OSError(msg)

            await to_thread(tmp_path.rename, path)

            # Update `_total_bytes` depending on whether the key existed already or not.
            if key in self._files:
                self._total_size -= self._files[key].size
            self._total_size += size

            # Update internal file dictionary.
            self._files[key] = File(path, size)

            # If size is too large now, remove items until it is less than or equal to the defined maximum.
            while self._total_size > self.max_size:
                # Delete the current oldest item, by instantiating an iterator over all keys (in order)
                # and passing its next item (i.e. the first one in order) to self.remove().
                await self._remove(next(iter(self._files)))

            return path

    @property
    def total_size(self) -> int:
        return self._total_size

    @property
    def files(self) -> OrderedDict[Path, File]:
        return self._files


class LRUCache:
    """A file-based LRU cache which is supervised by a `LRUCacheSupervisor` instance.

    The cached files are stored in a subdirectory of the `LRUCacheSupervisor`.

    Look at the `LRUCacheSupervisor` class for more information about the methods.
    """

    def __init__(self, supervisor: LRUCacheSupervisor, subdirectory: Path, extension: str = "") -> None:
        self._supervisor = supervisor
        self._subdirectory = subdirectory
        self._extension = extension

        self._supervisor.register(self._subdirectory)

    def set_on_remove_callback(self, callback: OnRemoveCallback) -> None:
        self._supervisor.set_on_remove_callback(self._subdirectory, callback)

    async def put(self, key: str, value: bytes) -> Path:
        return await self._supervisor.put(self._subdirectory / key, value, self._extension)

    def get(self, key: str) -> Path:
        return self._supervisor.get(self._subdirectory / key)

    async def remove(self, key: str) -> None:
        await self._supervisor.remove(self._subdirectory / key)

    def contains(self, key: str) -> bool:
        return self._supervisor.contains(self._subdirectory / key)

    @property
    def files(self) -> dict[str, File]:
        return {
            key.stem: file for key, file in self._supervisor.files.items() if key.is_relative_to(self._subdirectory)
        }

    @property
    def directory(self) -> Path:
        return self._supervisor.directory / self._subdirectory
