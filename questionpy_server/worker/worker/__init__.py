from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Optional, TypeVar, Any

from questionpy_common.elements import OptionsFormDefinition
from questionpy_common.manifest import Manifest

from questionpy_server.worker import WorkerResources, WorkerResourceLimits
from questionpy_server.worker.runtime.messages import MessageToWorker, MessageToServer

_T = TypeVar("_T", bound=MessageToServer)


class WorkerState(Enum):
    NOT_RUNNING = 1
    IDLE = 2
    SERVER_AWAITS_RESPONSE = 3  # server send a message to worker and is waiting for a response
    WORKER_AWAITS_RESPONSE = 4  # worker send a request/message to server and server is now processing the request


class Worker(ABC):
    """Interface for worker implementations."""

    def __init__(self, package: Path, limits: Optional[WorkerResourceLimits]) -> None:
        self.package = package
        self.limits = limits
        self.state = WorkerState.NOT_RUNNING

    @abstractmethod
    async def start(self) -> None:
        """Start and initialize the worker process.

        Only after this method finishes is the worker ready to accept other messages.
        """

    @abstractmethod
    async def stop(self, timeout: float) -> None:
        """Ask the worker to exit gracefully and wait for at most timeout seconds before killing it.

        If the worker is not running for any reason, this method should do nothing.
        """

    @abstractmethod
    async def kill(self) -> None:
        """Kill the worker process without waiting for it to exit.

        If the worker is not running for any reason, this method should do nothing.
        """

    @abstractmethod
    def send(self, message: MessageToWorker) -> None:
        """Send a message to the worker."""

    @abstractmethod
    async def get_resource_usage(self) -> Optional[WorkerResources]:
        """Get the worker's current resource usage. If unknown or unsupported, return None."""

    @abstractmethod
    async def get_manifest(self) -> Manifest:
        """Get manifest of the main package in the worker."""

    @abstractmethod
    async def get_options_form_definition(self) -> OptionsFormDefinition:
        """Get the package options form definition."""

    @abstractmethod
    async def create_question_from_options(self, state: Optional[bytes], form_data: dict[str, Any]) -> str:
        pass
