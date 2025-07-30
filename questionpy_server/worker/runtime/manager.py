#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import dataclasses
import resource
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from graphlib import TopologicalSorter
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn, TypeVar, cast

from questionpy_common.constants import MAX_QPY_DEPENDENCY_LEVELS
from questionpy_common.environment import (
    Environment,
    OnRequestCallback,
    Package,
    PackageNamespaceAndShortName,
    PackageState,
    RequestUser,
    WorkerPermissions,
    set_qpy_environment,
)
from questionpy_common.manifest import PackageType
from questionpy_server.worker.runtime.connection import WorkerToServerConnection
from questionpy_server.worker.runtime.messages import (
    CreateQuestionFromOptions,
    Exit,
    GetOptionsForm,
    GetQPyPackageManifest,
    InitWorker,
    LoadQPyPackage,
    MessageIds,
    MessageToServer,
    MessageToWorker,
    ScoreAttempt,
    StartAttempt,
    ViewAttempt,
    WorkerError,
)
from questionpy_server.worker.runtime.package import ImportablePackage, NoInitFunctionError, open_qpy_package
from questionpy_server.worker.runtime.package_location import PackageLocation

if TYPE_CHECKING:
    from questionpy_common.api.qtype import QuestionTypeInterface

__all__ = ["WorkerManager"]


@dataclass(frozen=True)
class EnvironmentImpl(Environment):
    _type: str
    _packages: dict[PackageNamespaceAndShortName, ImportablePackage]
    _on_request_callbacks: list[OnRequestCallback]
    _main_package: ImportablePackage | None = None
    _request_user: RequestUser | None = None
    _permissions: WorkerPermissions | None = None

    @property
    def type(self) -> str:
        return self._type

    @property
    def packages(self) -> Mapping[PackageNamespaceAndShortName, Package]:
        return MappingProxyType(self._packages)

    @property
    def main_package(self) -> Package:
        if not self._main_package:
            raise MainPackageNotLoadedError

        return self._main_package

    @property
    def request_user(self) -> RequestUser | None:
        return self._request_user

    @property
    def permissions(self) -> WorkerPermissions | None:
        return self._permissions

    def register_on_request_callback(self, callback: OnRequestCallback) -> None:
        self._on_request_callbacks.append(callback)


M = TypeVar("M", bound=MessageToWorker)
type OnMessageCallback[M: MessageToWorker] = Callable[[M], MessageToServer]


def _linearize_packages(
    packages: Mapping[PackageNamespaceAndShortName, ImportablePackage],
) -> Sequence[PackageNamespaceAndShortName]:
    sorter = TopologicalSorter[PackageNamespaceAndShortName]()
    for nssn, package in packages.items():
        sorter.add(nssn, *package.dependencies.keys())

    return tuple(sorter.static_order())


class WorkerManager:
    def __init__(self, server_connection: WorkerToServerConnection):
        self._connection = server_connection

        self._packages: dict[PackageNamespaceAndShortName, ImportablePackage] = {}

        self._worker_home: Path | None = None

        self._env: EnvironmentImpl | None = None
        self._question_type: QuestionTypeInterface | None = None

        self._message_dispatch: dict[MessageIds, OnMessageCallback] = {
            LoadQPyPackage.message_id: self.on_msg_load_qpy_package,
            GetQPyPackageManifest.message_id: self.on_msg_get_qpy_package_manifest,
            GetOptionsForm.message_id: self.on_msg_get_options_form_definition,
            CreateQuestionFromOptions.message_id: self.on_msg_create_question_from_options,
            StartAttempt.message_id: self.on_msg_start_attempt,
            ViewAttempt.message_id: self.on_msg_view_attempt,
            ScoreAttempt.message_id: self.on_msg_score_attempt,
        }

        self._on_request_callbacks: list[OnRequestCallback] = []

    def bootstrap(self) -> None:
        init_msg = self._connection.receive_message()
        if not isinstance(init_msg, InitWorker):
            raise self._raise_not_initialized(init_msg)

        self._worker_home = init_msg.worker_home

        if init_msg.permissions:
            # Limit memory usage.
            resource.setrlimit(resource.RLIMIT_AS, (init_msg.permissions.memory, init_msg.permissions.memory))

        self._env = EnvironmentImpl(
            _type=init_msg.worker_type,
            _permissions=init_msg.permissions,
            _packages=self._packages,
            _on_request_callbacks=self._on_request_callbacks,
        )
        set_qpy_environment(self._env)

        self._connection.send_message(InitWorker.Response())

    def loop(self) -> None:
        """Dispatch incoming messages."""
        while True:
            msg = self._connection.receive_message()
            if isinstance(msg, Exit):
                return

            try:
                response = self._message_dispatch[msg.message_id](msg)
            except Exception as error:  # noqa: BLE001
                response = WorkerError.from_exception(error, cause=msg)
            self._connection.send_message(response)

    @staticmethod
    def _open_package(location: PackageLocation, worker_home: Path) -> ImportablePackage:
        # This is a separate method to allow it to be mocked separately.
        return open_qpy_package(location, worker_home)

    def _open_packages_recursively(
        self,
        msg: LoadQPyPackage,
        package_location: PackageLocation,
        stack: tuple[PackageNamespaceAndShortName, ...] = (),
    ) -> tuple[PackageNamespaceAndShortName, ImportablePackage]:
        if not self._env or not self._worker_home:
            self._raise_not_initialized(msg)

        package = self._open_package(package_location, self._worker_home)
        nssn = PackageNamespaceAndShortName(package.manifest.namespace, package.manifest.short_name)

        if nssn in stack and self._packages[nssn].manifest.version == package.manifest.version:
            raise CircularDependencyError(nssn, stack)

        if nssn in self._packages:
            # For now, we don't support two packages using the same static dependency, even if they would use the same
            # version. Supporting the latter case would require us to either trust or check that both dependency's
            # content is identical.
            err_msg = f"Package '{nssn}' is already loaded. Dependency stack: {stack}"
            raise DependencyError(err_msg, stack)

        self._packages[nssn] = package

        new_stack = (*stack, nssn)

        if len(stack) >= MAX_QPY_DEPENDENCY_LEVELS and package.manifest.dependencies.qpy:
            raise TooDeeplyNestedDependencyError(new_stack)

        for dep_location in package.resolve_static_dependencies():
            dep_nssn, dep_package = self._open_packages_recursively(msg, dep_location, new_stack)
            package.dependencies[dep_nssn] = dep_package

        return nssn, package

    def on_msg_load_qpy_package(self, msg: LoadQPyPackage) -> MessageToServer:
        if not self._env or not self._worker_home:
            self._raise_not_initialized(msg)

        root_nssn, root_package = self._open_packages_recursively(msg, msg.location, ())

        if msg.main:
            self._env = dataclasses.replace(self._env, _main_package=root_package)
            set_qpy_environment(self._env)

        linearized = _linearize_packages(self._packages)
        for nssn in linearized:
            package = self._packages[nssn]
            if package.state < PackageState.LOADED:
                package.load()

            if package.state < PackageState.INITIALIZED:
                is_question_like = package.manifest.type in {PackageType.QUESTION, PackageType.QUESTIONTYPE}
                try:
                    package.init(self._env)
                except NoInitFunctionError:
                    if is_question_like:
                        # Questions and question types MUST have init functions. (Others MAY.)
                        raise

                if package is root_package and msg.main and is_question_like:
                    self._question_type = cast("QuestionTypeInterface", package.interface)

        return LoadQPyPackage.Response(root_nssn=root_nssn, loaded_packages=linearized)

    def on_msg_get_qpy_package_manifest(self, msg: GetQPyPackageManifest) -> MessageToServer:
        if not self._env:
            self._raise_not_initialized(msg)

        return GetQPyPackageManifest.Response(manifest=self._env.main_package.manifest)

    def on_msg_get_options_form_definition(self, msg: GetOptionsForm) -> MessageToServer:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg, msg.request_user):
            definition, form_data = self._question_type.get_options_form(msg.question_state)

            return GetOptionsForm.Response(definition=definition, form_data=form_data)

    def on_msg_create_question_from_options(self, msg: CreateQuestionFromOptions) -> CreateQuestionFromOptions.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg, msg.request_user):
            question = self._question_type.create_question_from_options(msg.question_state, msg.form_data)

            return CreateQuestionFromOptions.Response(
                question_state=question.export_question_state(), question_model=question.export()
            )

    def on_msg_start_attempt(self, msg: StartAttempt) -> StartAttempt.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg, msg.request_user):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_started_model = question.start_attempt(msg.variant)
            return StartAttempt.Response(attempt_started_model=attempt_started_model)

    def on_msg_view_attempt(self, msg: ViewAttempt) -> ViewAttempt.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg, msg.request_user):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_model = question.get_attempt(msg.attempt_state, msg.scoring_state, msg.response)
            return ViewAttempt.Response(attempt_model=attempt_model)

    def on_msg_score_attempt(self, msg: ScoreAttempt) -> ScoreAttempt.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg, msg.request_user):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_scored_model = question.score_attempt(msg.attempt_state, msg.scoring_state, msg.response)
            return ScoreAttempt.Response(attempt_scored_model=attempt_scored_model)

    @staticmethod
    def _raise_not_initialized(msg: MessageToWorker) -> NoReturn:
        errmsg = f"'{InitWorker.__name__}' message expected, '{type(msg).__name__}' received"
        raise WorkerNotInitializedError(errmsg)

    @staticmethod
    def _raise_no_main_package_loaded(msg: MessageToWorker) -> NoReturn:
        errmsg = f"'{LoadQPyPackage.__name__}(main=True)' message expected, '{type(msg).__name__}' received"
        raise MainPackageNotLoadedError(errmsg)

    @contextmanager
    def _with_request_user(self, msg: MessageToWorker, request_user: RequestUser) -> Generator[None, None, None]:
        if not self._env:
            self._raise_not_initialized(msg)

        if self._env.request_user:
            err_msg = "There is already a request_user in the current environment."
            raise RuntimeError(err_msg)

        self._env = dataclasses.replace(self._env, _request_user=request_user)
        set_qpy_environment(self._env)
        try:
            for callback in self._on_request_callbacks:
                callback(request_user)

            yield
        finally:
            self._env = dataclasses.replace(self._env, _request_user=None)
            set_qpy_environment(self._env)


class PackageInitFailedError(Exception):
    pass


class WorkerNotInitializedError(Exception):
    pass


class MainPackageNotLoadedError(Exception):
    pass


class DependencyError(Exception):
    def __init__(self, message: str, stack: tuple[PackageNamespaceAndShortName, ...]) -> None:
        super().__init__(message)
        self.stack = stack


class CircularDependencyError(DependencyError):
    def __init__(self, nssn: PackageNamespaceAndShortName, stack: tuple[PackageNamespaceAndShortName, ...]):
        super().__init__(f"'{nssn}'. Dependency stack: {stack}", stack)


class TooDeeplyNestedDependencyError(DependencyError):
    def __init__(self, stack: tuple[PackageNamespaceAndShortName, ...]) -> None:
        super().__init__(f"Dependency graph is deeper than '{MAX_QPY_DEPENDENCY_LEVELS}' levels at '{stack}'.", stack)
