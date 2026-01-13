#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import dataclasses
import resource
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from graphlib import TopologicalSorter
from itertools import chain
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn, TypeVar, cast

from questionpy_common import PackageNamespaceAndShortName
from questionpy_common.dependencies import SolutionAndLocation, StaticDependencySolution
from questionpy_common.environment import (
    Environment,
    OnRequestCallback,
    Package,
    PackagePermissions,
    PackageState,
    RequestInfo,
    set_qpy_environment,
)
from questionpy_common.manifest import PackageType
from questionpy_common.package_location import PackageLocation
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

if TYPE_CHECKING:
    from questionpy_common.api.qtype import QuestionTypeInterface

__all__ = ["WorkerManager"]


@dataclass(frozen=True)
class EnvironmentImpl(Environment):
    _type: str
    _packages: dict[PackageNamespaceAndShortName, ImportablePackage]
    _on_request_callbacks: list[OnRequestCallback]
    _permissions: PackagePermissions
    _main_package: ImportablePackage | None = None
    _request_info: RequestInfo | None = None

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
    def request_info(self) -> RequestInfo | None:
        return self._request_info

    @property
    def permissions(self) -> PackagePermissions:
        return self._permissions

    def register_on_request_callback(self, callback: OnRequestCallback) -> None:
        self._on_request_callbacks.append(callback)


M = TypeVar("M", bound=MessageToWorker)
type OnMessageCallback[M: MessageToWorker] = Callable[[M], MessageToServer]


def _linearize_dependencies(
    solutions: Mapping[PackageNamespaceAndShortName, SolutionAndLocation],
) -> Sequence[PackageNamespaceAndShortName]:
    sorter = TopologicalSorter[PackageNamespaceAndShortName]()

    for nssn, (solution, _) in solutions.items():
        dep_nssns = [PackageNamespaceAndShortName(dep.namespace, dep.short_name) for dep in solution.dependencies.qpy]
        sorter.add(nssn, *dep_nssns)

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

        if init_msg.worker_type != "thread":
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

    def _init_package(self, nssn: PackageNamespaceAndShortName, env: Environment) -> None:
        package = self._packages[nssn]

        # Make the package's dependencies accessible to the package.
        for dep in package.manifest.dependencies.qpy:
            dep_nssn = PackageNamespaceAndShortName(dep.namespace, dep.short_name)
            dep_package = self._packages.get(dep_nssn)
            if not dep_package:
                err_msg = f"Unfulfilled dependency of '{nssn}': '{dep_nssn}'"
                raise RuntimeError(err_msg)

            package.dependencies[dep_nssn] = dep_package

        if package.state < PackageState.LOADED:
            package.load()

        if package.state < PackageState.INITIALIZED:
            is_question_like = package.manifest.type in {PackageType.QUESTION, PackageType.QUESTIONTYPE}
            try:
                package.init(env)
            except NoInitFunctionError:
                if is_question_like:
                    # Questions and question types MUST have init functions. (Others MAY.)
                    raise

            if package is env.main_package and is_question_like:
                self._question_type = cast("QuestionTypeInterface", package.interface)

    def on_msg_load_qpy_package(self, msg: LoadQPyPackage) -> MessageToServer:
        if not self._env or not self._worker_home:
            self._raise_not_initialized(msg)

        root_package = self._open_package(msg.location, self._worker_home)
        root_nssn = root_package.manifest.nssn
        self._packages[root_nssn] = root_package

        linearized = _linearize_dependencies(msg.dependencies)

        for nssn in reversed(linearized):
            solution, package_location = msg.dependencies[nssn]
            if isinstance(solution, StaticDependencySolution):
                owner = self._packages.get(solution.owner)
                if not owner:
                    # Since we open packages in reverse topological order, this shouldn't happen.
                    # (Unless the tree passed to us by the server contains errors.)
                    err_msg = f"Cannot open static dependency '{nssn}' before owner '{solution.owner}'."
                    raise RuntimeError(err_msg)

                package_location = owner.resolve_static_dependency(nssn)

            # MyPy doesn't narrow the type properly.
            self._packages[nssn] = self._open_package(cast("PackageLocation", package_location), self._worker_home)

        if msg.main:
            self._env = dataclasses.replace(self._env, _main_package=root_package)
            set_qpy_environment(self._env)

        for nssn in chain(linearized, (root_nssn,)):
            self._init_package(nssn, self._env)

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

        with self._with_request_info(msg, msg.request_info):
            definition, form_data = self._question_type.get_options_form(msg.question_state)

            return GetOptionsForm.Response(definition=definition, form_data=form_data)

    def on_msg_create_question_from_options(self, msg: CreateQuestionFromOptions) -> CreateQuestionFromOptions.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_info(msg, msg.request_info):
            question = self._question_type.create_question_from_options(msg.question_state, msg.form_data)

            return CreateQuestionFromOptions.Response(
                question_state=question.export_question_state(), question_model=question.export()
            )

    def on_msg_start_attempt(self, msg: StartAttempt) -> StartAttempt.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_info(msg, msg.request_info):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_started_model = question.start_attempt(msg.variant)
            return StartAttempt.Response(attempt_started_model=attempt_started_model)

    def on_msg_view_attempt(self, msg: ViewAttempt) -> ViewAttempt.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_info(msg, msg.request_info):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_model = question.get_attempt(msg.attempt_state, msg.scoring_state, msg.response)
            return ViewAttempt.Response(attempt_model=attempt_model)

    def on_msg_score_attempt(self, msg: ScoreAttempt) -> ScoreAttempt.Response:
        if not self._env:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_info(msg, msg.request_info):
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
    def _with_request_info(self, msg: MessageToWorker, request_info: RequestInfo) -> Generator[None, None, None]:
        if not self._env:
            self._raise_not_initialized(msg)

        if self._env.request_info:
            err_msg = "There is already a request_info in the current environment."
            raise RuntimeError(err_msg)

        self._env = dataclasses.replace(self._env, _request_info=request_info)
        set_qpy_environment(self._env)
        try:
            for callback in self._on_request_callbacks:
                callback(request_info)

            yield
        finally:
            self._env = dataclasses.replace(self._env, _request_info=None)
            set_qpy_environment(self._env)


class PackageInitFailedError(Exception):
    pass


class WorkerNotInitializedError(Exception):
    pass


class MainPackageNotLoadedError(Exception):
    pass
