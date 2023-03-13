import asyncio
import logging
import os
from abc import abstractmethod
from io import BufferedReader, FileIO
from typing import Protocol, Optional

log = logging.getLogger(__name__)


class SupportsWrite(Protocol):
    @abstractmethod
    def write(self, data: bytes) -> Optional[int]:
        pass


class SupportsRead(Protocol):
    @abstractmethod
    def read(self, size: int) -> bytes:
        pass


class SupportsAsyncRead(Protocol):
    @abstractmethod
    async def readexactly(self, size: int) -> bytes:
        pass


class DuplexPipe:
    """Simple combination of two OS pipes that can be thought of and used as one duplex pipe."""

    class Side(SupportsRead, SupportsWrite):
        """One side of a duplex pipe.

        Uses the receive side of one pipe and the transmit side of the other to provide file-like read and write
        methods.
        """

        def __init__(self, receive: BufferedReader, transmit: FileIO):
            self._receive = receive
            self._transmit = transmit

        def read(self, size: int) -> bytes:
            """Reads exactly size bytes.

            :raises EOFError: if EOF is reached before `size` bytes are read
            """
            read = self._receive.read(size)
            if len(read) < size:
                raise EOFError
            return read

        def write(self, data: bytes) -> int:
            """Writes data to the pipe completely."""
            view = memoryview(data)
            size = len(data)
            written = 0
            while written < size:
                written += self._transmit.write(view[written:])

            return written

    def __init__(self, pipe1: tuple[BufferedReader, FileIO], pipe2: tuple[BufferedReader, FileIO]) -> None:
        self._pipe1 = pipe1
        self._pipe2 = pipe2

        self.left = self.Side(pipe1[0], pipe2[1])
        self.right = self.Side(pipe2[0], pipe1[1])

    @classmethod
    def open(cls) -> "DuplexPipe":
        """Opens two pipes and joins them into one DuplexPipe."""
        return DuplexPipe(cls._open_pipe(), cls._open_pipe())

    @classmethod
    def _open_pipe(cls) -> tuple[BufferedReader, FileIO]:
        rx_fd, tx_fd = os.pipe()
        return os.fdopen(rx_fd, "rb"), os.fdopen(tx_fd, "wb", buffering=0)

    def close(self) -> None:
        """Closes both sides of both pipes."""
        # If we close an rx side which is currently being read from, close() blocks until that read ends.
        # So we close the tx sides first, causing the rx sides to receive EOFs.
        self._pipe1[1].close()
        self._pipe2[1].close()
        self._pipe1[0].close()
        self._pipe2[0].close()


class AsyncReadAdapter(SupportsAsyncRead):
    def __init__(self, read: SupportsRead) -> None:
        self._read = read

    async def readexactly(self, size: int) -> bytes:
        return await asyncio.to_thread(lambda: self._read.read(size))
