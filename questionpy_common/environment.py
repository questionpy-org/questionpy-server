#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from importlib.resources.abc import Traversable
from typing import NamedTuple, Protocol

from questionpy_common.api.package import QPyPackageInterface
from questionpy_common.manifest import Bcp47LanguageTag, Manifest

__all__ = [
    "Environment",
    "NoEnvironmentError",
    "OnRequestCallback",
    "Package",
    "PackageInitFunction",
    "PackageNamespaceAndShortName",
    "PackageNotInitializedError",
    "PackageNotLoadedError",
    "PackageState",
    "RequestUser",
    "WorkerResourceLimits",
    "get_qpy_environment",
    "set_qpy_environment",
]


@dataclass
class RequestUser:
    """Preferences of the user that a request is being processed for."""

    preferred_languages: Sequence[Bcp47LanguageTag]


@dataclass
class WorkerResourceLimits:
    """Maximum resources that a worker process is allowed to consume."""

    max_memory: int
    max_cpu_time_seconds_per_call: float


@total_ordering
class PackageState(Enum):
    OPENED = 1
    """The package is present and in the process of being loaded, but none of its code has been executed yet."""
    LOADED = 2
    """The package entrypoint has been imported."""
    INITIALIZED = 3
    """The package's `init` function, if any, has been executed."""

    def __lt__(self, other: object) -> bool:
        if isinstance(other, PackageState):
            return self.value < other.value
        return NotImplemented


class PackageNamespaceAndShortName(NamedTuple):
    """Tuple of namespace and short name, identifying any version of a specific package."""

    namespace: str
    short_name: str

    def __str__(self) -> str:
        return f"@{self.namespace}/{self.short_name}"


class Package(Protocol):
    @property
    def manifest(self) -> Manifest: ...

    def get_path(self, path: str) -> Traversable:
        """Gets a [Traversable][] object which allows reading files from the package.

        Note that the returned path object may not exist. This method does not throw an exception in that case.

        Args:
            path: Path relative to the root of the package.
        """

    @property
    def state(self) -> PackageState: ...

    @property
    def interface(self) -> QPyPackageInterface:
        """Gives access to the package's outward interface.

        Raises:
            PackageNotInitializedError
        """

    @property
    def dependencies(self) -> Mapping[PackageNamespaceAndShortName, "Package"]:
        """The direct QPy dependencies of this package."""


type OnRequestCallback = Callable[[RequestUser], None]


class Environment(Protocol):
    @property
    def type(self) -> str:
        """The kind of worker we are running in.

        The well-known values are:

        - process: The worker is running in a subprocess of the server process.
        - thread: The worker is running in a thread of the server process. Should only be used for debugging since it is
          not possible to isolate workers effectively.
        - container: The worker is sandboxed in a Docker(-like) container.

        Other worker types may be added in the future. (Hence the `str` type.)
        """

    @property
    def limits(self) -> WorkerResourceLimits | None:
        """The resource limits imposed on the worker, if any."""

    @property
    def request_user(self) -> RequestUser | None:
        """If the worker is currently processing a request, information about the user that it is being processed for.

        When no request is being processed (such as during a call to the package's `init` function), this will be None.
        """

    @property
    def main_package(self) -> Package:
        """The main package in this worker."""

    @property
    def packages(self) -> Mapping[PackageNamespaceAndShortName, Package]:
        """All packages loaded in the worker, including the main package.

        Keys are the package namespace and short name. Only one version of a package can be loaded at a time. This may
        include packages which are not yet initialized (i.e. their `init` function has not finished yet).
        """

    def register_on_request_callback(self, callback: OnRequestCallback) -> None:
        """Register a new on-request callback.

        When processing of a new request begins, any callback(s) registered here are called to inform packages of the
        new [RequestUser][]. This may be expanded in the future to allow cleaning up after request processing has
        finished.
        """


type PackageInitFunction = (
    Callable[[Package, Environment], QPyPackageInterface]
    | Callable[[Package], QPyPackageInterface]
    | Callable[[], QPyPackageInterface]
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


class PackageNotInitializedError(Exception):
    """The package's state was not INITIALIZED."""


class PackageNotLoadedError(Exception):
    """The package's state was not LOADED or higher."""
