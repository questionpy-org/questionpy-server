#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import json
from typing import AsyncIterator

from questionpy_server.utils.streams import SupportsAsyncRead, SupportsWrite
from questionpy_server.worker.runtime.connection import send_message
from questionpy_server.worker.runtime.messages import MessageToServer, MessageToWorker, messages_header_struct, \
    InvalidMessageIdError


class ServerToWorkerConnection(AsyncIterator[MessageToServer]):
    # pylint: disable=duplicate-code
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
            raise ConnectionError()

        header_bytes = await self.stream_in.readexactly(messages_header_struct.size)
        message_id, length = messages_header_struct.unpack(header_bytes)
        message_type = MessageToServer.types.get(message_id, None)
        if message_type is None:
            self.stream_in_invalid_state = True
            raise InvalidMessageIdError(message_id, length)

        if length:
            json_data = await self.stream_in.readexactly(length)
            json_obj = json.loads(json_data)
            return message_type.parse_obj(json_obj)

        return message_type()

    def __aiter__(self) -> AsyncIterator[MessageToServer]:
        return self

    async def __anext__(self) -> MessageToServer:
        try:
            return await self.receive_message()
        except EOFError as e:
            # Didn't read a complete header before EOF. The worker probably exited, stop iterating.
            raise StopAsyncIteration from e
