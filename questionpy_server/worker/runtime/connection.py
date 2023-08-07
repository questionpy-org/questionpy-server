#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from questionpy_server.utils.streams import SupportsWrite, SupportsRead
from questionpy_server.worker.runtime.messages import Message, get_message_bytes, MessageToServer, MessageToWorker, \
    messages_header_struct, InvalidMessageIdError


def send_message(message: Message, out: SupportsWrite) -> None:
    """Send a message to out."""
    header, json_bytes = get_message_bytes(message)
    out.write(header)
    if json_bytes:
        out.write(json_bytes)


class WorkerToServerConnection:
    # pylint: disable=duplicate-code
    """Controls the connection (stdin/stdout pipes) from a worker to the server.
    stream_in must be buffered as we want to be able to read exactly the given number of bytes.
    """

    def __init__(self, stream_in: SupportsRead, stream_out: SupportsWrite):
        self.stream_in: SupportsRead = stream_in
        self.stream_out: SupportsWrite = stream_out
        self.stream_in_invalid_state: bool = False

    def send_message(self, message: MessageToServer) -> None:
        """Send a message to the server."""
        send_message(message, self.stream_out)

    def receive_message(self) -> MessageToWorker:
        """Receive a message from the server."""
        if self.stream_in_invalid_state:
            raise ConnectionError()

        header_bytes = self.stream_in.read(messages_header_struct.size)
        if header_bytes is None or len(header_bytes) != messages_header_struct.size:
            self.stream_in_invalid_state = True
            raise BrokenPipeError()

        message_id, length = messages_header_struct.unpack(header_bytes)
        message_type = MessageToWorker.types.get(message_id, None)
        if message_type is None:
            self.stream_in_invalid_state = True
            raise InvalidMessageIdError(message_id, length)

        if length:
            json_data = self.stream_in.read(length)
            if json_data is None or len(json_data) != length:
                self.stream_in_invalid_state = True
                raise BrokenPipeError()

            return message_type.model_validate_json(json_data)

        return message_type()
