import json
import resource
import sys
from dataclasses import dataclass
from io import BufferedReader, RawIOBase
from pathlib import Path
from typing import Any, Optional, Union, Callable, TypeVar, TYPE_CHECKING

from questionpy_common.misc import Size

from .messages import InitWorker, Exit, get_message_bytes, messages_header_struct, Message, MessageIds, \
    MessageToWorker, MessageToServer, InvalidMessageIdError, GetQPyPackageManifest, LoadQPyPackage, \
    GetOptionsFormDefinition, WorkerError
from .package import QPyPackage, QPyMainPackage

if TYPE_CHECKING:
    from asyncio import StreamWriter


@dataclass
class WorkerResourceLimits:
    """Maximum resources that a worker process is allowed to consume."""
    max_memory: Size
    max_cpu_time_seconds_per_call: float


def send_message(message: Message, out: Union[RawIOBase, "StreamWriter"]) -> None:
    """Send a message to out."""
    header, json_bytes = get_message_bytes(message)
    out.write(header)
    if json_bytes:
        out.write(json_bytes)


class WorkerToServerConnection:
    """
    Controls the connection (stdin/stdout pipes) from a worker to the server.
    stream_in must be buffered as we want to be able to read exactly the given number of bytes.
    """

    def __init__(self, stream_in: BufferedReader, stream_out: RawIOBase):
        self.stream_in: BufferedReader = stream_in
        self.stream_out: RawIOBase = stream_out
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

            json_obj = json.loads(json_data)
            return message_type(**json_obj)

        return message_type()


_M = TypeVar('_M', bound=MessageToServer)


class WorkerManager:
    def __init__(self, server_connection: WorkerToServerConnection):
        self.server_connection: WorkerToServerConnection = server_connection
        self.limits: Optional[WorkerResourceLimits] = None
        self.loaded_packages: dict[str, QPyPackage] = {}
        self.main_package: Optional[QPyMainPackage] = None
        self.message_dispatch: dict[MessageIds, Callable[[Any], MessageToServer]] = {
            LoadQPyPackage.message_id: self.on_msg_load_qpy_package,
            GetQPyPackageManifest.message_id: self.on_msg_get_qpy_package_manifest,
            GetOptionsFormDefinition.message_id: self.on_msg_get_options_form_definition,
        }

    def bootstrap(self) -> None:
        init_msg = self.server_connection.receive_message()
        if not isinstance(init_msg, InitWorker):
            raise BootstrapError()

        self.limits = WorkerResourceLimits(max_memory=Size(init_msg.max_memory),
                                           max_cpu_time_seconds_per_call=init_msg.max_cpu_time)
        # Limit memory usage.
        resource.setrlimit(resource.RLIMIT_AS, (self.limits.max_memory, self.limits.max_memory))

        self.server_connection.send_message(InitWorker.Response())

    def loop(self) -> None:
        """Dispatch incoming messages."""
        while True:
            msg = self.server_connection.receive_message()
            if isinstance(msg, Exit):
                sys.exit(0)
            else:
                try:
                    response = self.message_dispatch[msg.message_id](msg)
                except Exception as error:  # pylint: disable=broad-except
                    response = WorkerError.from_exception(error, cause=msg)
                self.server_connection.send_message(response)

    def on_msg_load_qpy_package(self, msg: LoadQPyPackage) -> MessageToServer:
        package: QPyPackage
        if msg.main:
            package = QPyMainPackage(Path(msg.path))
            self.main_package = package
        else:
            package = QPyPackage(Path(msg.path))
        self.loaded_packages[msg.path] = package

        return LoadQPyPackage.Response()

    def on_msg_get_qpy_package_manifest(self, msg: GetQPyPackageManifest) -> MessageToServer:
        package = self.loaded_packages[msg.path]
        return GetQPyPackageManifest.Response(manifest=package.manifest)

    def on_msg_get_options_form_definition(self, _msg: GetOptionsFormDefinition) -> MessageToServer:
        if self.main_package is None:
            raise MainPackageNotLoadedError()
        definition = self.main_package.get_options_form_definition()
        return GetOptionsFormDefinition.Response(definition=definition)


class BootstrapError(Exception):
    pass


class MainPackageNotLoadedError(Exception):
    pass
