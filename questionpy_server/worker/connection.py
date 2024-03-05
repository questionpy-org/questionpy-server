#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from collections.abc import AsyncIterator
from typing import Self

from questionpy_server.worker.runtime.connection import send_message
from questionpy_server.worker.runtime.messages import (
    InvalidMessageIdError,
    MessageToServer,
    MessageToWorker,
    messages_header_struct,
)
from questionpy_server.worker.runtime.streams import SupportsAsyncRead, SupportsWrite


class ServerToWorkerConnection(AsyncIterator[MessageToServer]):
    """Controls the connection (stdin/stdout pipes) from the server to a worker."""

    def __init__(self, stream_in: SupportsAsyncRead, stream_out: SupportsWrite):
        self.stream_in: SupportsAsyncRead = stream_in
        self.stream_out: SupportsWrite = stream_out
        self.stream_in_invalid_state: bool = False

    def send_message(self, message: MessageToWorker) -> None:
        """Send a message to a worker."""
        send_message(message, self.stream_out)

    async def receive_message(self) -> MessageToServer:
        """Receive a message from a worker."""
        if self.stream_in_invalid_state:
            raise ConnectionError

        header_bytes = await self.stream_in.readexactly(messages_header_struct.size)
        message_id, length = messages_header_struct.unpack(header_bytes)
        message_type = MessageToServer.types.get(message_id, None)
        if message_type is None:
            self.stream_in_invalid_state = True
            raise InvalidMessageIdError(message_id, length)

        if length:
            json_data = await self.stream_in.readexactly(length)
            return message_type.model_validate_json(json_data)

        return message_type()

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> MessageToServer:
        try:
            return await self.receive_message()
        except EOFError as e:
            # Didn't read a complete header before EOF. The worker probably exited, stop iterating.
            raise StopAsyncIteration from e
