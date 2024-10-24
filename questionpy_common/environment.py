#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from abc import abstractmethod
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from typing import Protocol, TypeAlias

from questionpy_common.api.package import QPyPackageInterface
from questionpy_common.api.qtype import QuestionTypeInterface
from questionpy_common.manifest import Manifest

__all__ = [
    "Environment",
    "NoEnvironmentError",
    "OnRequestCallback",
    "Package",
    "PackageInitFunction",
    "RequestUser",
    "WorkerResourceLimits",
    "get_qpy_environment",
    "set_qpy_environment",
]


@dataclass
class RequestUser:
    """Preferences of the user that a request is being processed for."""

    preferred_languages: Sequence[str]


@dataclass
class WorkerResourceLimits:
    """Maximum resources that a worker process is allowed to consume."""

    max_memory: int
    max_cpu_time_seconds_per_call: float


class Package(Protocol):
    @property
    @abstractmethod
    def manifest(self) -> Manifest: ...

    @abstractmethod
    def get_path(self, path: str) -> Traversable:
        """Gets a [Traversable][] object which allows reading files from the package.

        Note that the returned path object may not exist. This method does not throw an exception in that case.

        Args:
            path: Path relative to the root of the package.
        """


OnRequestCallback: TypeAlias = Callable[[RequestUser], None]


class Environment(Protocol):
    type: str
    """The kind of worker we are running in.

    The well-known values are:

    - process: The worker is running in a subprocess of the server process.
    - thread: The worker is running in a thread of the server process. Should only be used for debugging since it is
      not possible to isolate workers effectively.
    - container: The worker is sandboxed in a Docker(-like) container.

    Other worker types may be added in future. (Hence the `str` type.)
    """
    limits: WorkerResourceLimits | None
    """The resource limits imposed on the worker, if any."""
    request_user: RequestUser | None
    """If the worker is currently processing a request, information about the user that it is being processed for.

    When no request is being processed (such as during a call to the package's `init` function), this will be None.
    """
    main_package: Package
    """The main package whose entrypoint was called."""
    packages: Mapping[str, Package]
    """All packages loaded in the worker, including the main package."""

    @abstractmethod
    def register_on_request_callback(self, callback: OnRequestCallback) -> None:
        """Register a new on-request callback.

        When processing of a new request begins, any callback(s) registered here are called to inform packages of the
        new [RequestUser][]. This may be expanded in the future to allow cleaning up after request processing has
        finished.
        """


PackageInitFunction: TypeAlias = (
    Callable[[Package, Environment], QPyPackageInterface]
    | Callable[[Package], QPyPackageInterface]
    | Callable[[], QuestionTypeInterface]
)
"""Signature of the "init"-function expected in the main package."""

_current_env: ContextVar[Environment | None] = ContextVar("_current_env")


def get_qpy_environment() -> Environment:
    """Retrieves the currently active QPy environment or raises an error if there is none.

    Raises:
        NoEnvironmentError: If no environment is active. You probably didn't call this method from a loaded package in
                            that case.
    """
    env = _current_env.get(None)
    if not env:
        msg = "No QPy environment is set in the current context"
        raise NoEnvironmentError(msg)
    return env


def set_qpy_environment(env: Environment | None) -> None:
    _current_env.set(env)


class NoEnvironmentError(Exception):
    pass
