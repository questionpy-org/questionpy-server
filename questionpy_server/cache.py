from collections import OrderedDict
from pathlib import Path
from typing import NamedTuple
from asyncio import gather, to_thread, Lock


class File(NamedTuple):
    path: Path
    size: int


class SizeError(Exception):
    def __init__(self, message: str = '', max_size: float = 0, actual_size: float = 0):
        super().__init__(message)

        self.max_size = max_size
        self.actual_size = actual_size


class FileLimitLRU:
    """
    Limit file cache size, evicting the least recently accessed file when the specified maximum is exceeded.
    Only `bytes` type values are accepted. Their size is calculated by passing them into the builtin `len()` function.
    """

    def __init__(self, directory: str, max_bytes: int, extension: str = None) -> None:
        """
        A cache should be initialised while starting a server therefore it is not necessary for it to be async.
        """

        self.max_bytes = max_bytes
        self._total_bytes = 0
        self._extension: str = '' if extension is None else '.' + extension.lstrip('.')

        self._files: OrderedDict[str, File] = OrderedDict()

        self.directory: Path = Path(directory).resolve()
        self.directory.mkdir(exist_ok=True)

        self._lock = Lock()

        for path in self.directory.iterdir():
            if not path.is_file():
                continue

            size = path.stat().st_size
            total = self._total_bytes + size

            # Remove files if cache is full.
            if total > self.max_bytes:
                path.unlink()
                continue

            self._total_bytes = total
            self._files[path.stem] = File(path, size)

    def contains(self, key: str) -> bool:
        """
        Checks if the file exists in cache and places it to the end ensuring that it is the most recent accessed file.
        """

        if key not in self._files:
            return False

        self._files.move_to_end(key)
        return True

    def _get_file(self, key: str) -> File:
        if not self.contains(key):
            raise FileNotFoundError

        return self._files[key]

    def get(self, key: str) -> Path:
        return self._get_file(key).path

    async def remove(self, key: str) -> None:
        """
        Removes file from the cache and the filesystem.
        """

        file = self._get_file(key)
        await to_thread(file.path.unlink, missing_ok=True)
        self._total_bytes -= file.size
        del self._files[key]

    async def clear(self) -> None:
        await gather(*[to_thread(file.path.unlink, missing_ok=True) for file in self._files.values()])
        self._total_bytes = 0
        self._files.clear()

    async def put(self, key: str, value: bytes) -> Path:
        """
        Only accepts `bytes` objects as values; raises a `TypeError` otherwise.
        If the length/size of the provided `value` exceeds `.max_bytes` a `SizeError` is raised.
        The internal `._total_bytes` attribute is updated.
        If the key existed before and just the value is replaced, the item is treated as most recently accessed and
        thus moved to the end of the internal linked list.
        If after adding the item `._total_bytes` exceeds `.max_bytes`, items are deleted in order from least to most
        recently accessed until the total size (in bytes) is in line with the specified maximum.
        """

        if not isinstance(value, bytes):
            raise TypeError("Not a bytes object:", repr(value))

        size = len(value)
        if size > self.max_bytes:
            # If we allowed this, the loop at the end would remove all items from the dictionary,
            # so we raise an error to allow exceptions for this case.
            raise SizeError(f"Item itself exceeds maximum allowed size of {self.max_bytes} bytes",
                            max_size=self.max_bytes, actual_size=size)

        async with self._lock:
            # Update `_total_bytes` depending on whether the key existed already or not.
            if key in self._files:
                self._total_bytes -= self._files[key].size
            self._total_bytes += size

            # Save the bytes on filesystem.
            path = self.directory / (key + self._extension)

            if not self.directory.is_dir():
                self.directory.mkdir(parents=True, exist_ok=True)

            if size != path.write_bytes(value):
                raise IOError("Failed to write bytes to file")

            # Update internal file dictionary.
            self._files[key] = File(path, size)

            # If size is too large now, remove items until it is less than or equal to the defined maximum.
            while self._total_bytes > self.max_bytes:
                # Delete the current oldest item, by instantiating an iterator over all keys (in order)
                # and passing its next item (i.e. the first one in order) to self.remove.
                try:
                    await self.remove(next(iter(self._files)))
                except FileNotFoundError:
                    # The file was deleted from the filesystem.
                    pass

            return path

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    @property
    def space_left(self) -> int:
        return self.max_bytes - self._total_bytes
