#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import resource
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import NoReturn, TypeAlias, TypeVar, cast

from questionpy_common.api.qtype import QuestionTypeInterface
from questionpy_common.environment import (
    Environment,
    OnRequestCallback,
    RequestUser,
    WorkerResourceLimits,
    get_qpy_environment,
    set_qpy_environment,
)
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
from questionpy_server.worker.runtime.package import ImportablePackage, load_package

__all__ = ["WorkerManager"]


@dataclass
class EnvironmentImpl(Environment):
    type: str
    main_package: ImportablePackage
    packages: dict[str, ImportablePackage]
    _on_request_callbacks: list[OnRequestCallback]
    request_user: RequestUser | None = None
    limits: WorkerResourceLimits | None = None

    def register_on_request_callback(self, callback: OnRequestCallback) -> None:
        self._on_request_callbacks.append(callback)


M = TypeVar("M", bound=MessageToWorker)
OnMessageCallback: TypeAlias = Callable[[M], MessageToServer]


class WorkerManager:
    def __init__(self, server_connection: WorkerToServerConnection):
        self._connection: WorkerToServerConnection = server_connection

        self._worker_type: str | None = None
        self._loaded_packages: dict[str, ImportablePackage] = {}

        self._limits: WorkerResourceLimits | None = None

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

        self._worker_type = init_msg.worker_type
        self._limits = init_msg.limits
        if self._limits:
            # Limit memory usage.
            resource.setrlimit(resource.RLIMIT_AS, (self._limits.max_memory, self._limits.max_memory))

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

    def on_msg_load_qpy_package(self, msg: LoadQPyPackage) -> MessageToServer:
        if not self._worker_type:
            self._raise_not_initialized(msg)

        package = load_package(msg.location)
        package.setup_imports()

        if msg.main:
            self._env = EnvironmentImpl(
                type=self._worker_type,
                limits=self._limits,
                packages=self._loaded_packages,
                main_package=package,
                _on_request_callbacks=self._on_request_callbacks,
            )
            set_qpy_environment(self._env)
        elif not self._env:
            self._raise_no_main_package_loaded(msg)

        package_interface = package.init(self._env)
        if msg.main:
            self._question_type = cast(QuestionTypeInterface, package_interface)

        self._loaded_packages[str(msg.location)] = package
        return LoadQPyPackage.Response()

    def on_msg_get_qpy_package_manifest(self, msg: GetQPyPackageManifest) -> MessageToServer:
        if not self._worker_type:
            self._raise_not_initialized(msg)

        package = self._loaded_packages[msg.path]
        return GetQPyPackageManifest.Response(manifest=package.manifest)

    def on_msg_get_options_form_definition(self, msg: GetOptionsForm) -> MessageToServer:
        if not self._worker_type:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg.request_user):
            definition, form_data = self._question_type.get_options_form(msg.question_state)

            return GetOptionsForm.Response(definition=definition, form_data=form_data)

    def on_msg_create_question_from_options(self, msg: CreateQuestionFromOptions) -> CreateQuestionFromOptions.Response:
        if not self._worker_type:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg.request_user):
            question = self._question_type.create_question_from_options(msg.question_state, msg.form_data)

            return CreateQuestionFromOptions.Response(
                question_state=question.export_question_state(), question_model=question.export()
            )

    def on_msg_start_attempt(self, msg: StartAttempt) -> StartAttempt.Response:
        if not self._worker_type:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg.request_user):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_started_model = question.start_attempt(msg.variant)
            return StartAttempt.Response(attempt_started_model=attempt_started_model)

    def on_msg_view_attempt(self, msg: ViewAttempt) -> ViewAttempt.Response:
        if not self._worker_type:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg.request_user):
            question = self._question_type.create_question_from_state(msg.question_state)
            attempt_model = question.get_attempt(msg.attempt_state, msg.scoring_state, msg.response)
            return ViewAttempt.Response(attempt_model=attempt_model)

    def on_msg_score_attempt(self, msg: ScoreAttempt) -> ScoreAttempt.Response:
        if not self._worker_type:
            self._raise_not_initialized(msg)
        if not self._question_type:
            self._raise_no_main_package_loaded(msg)

        with self._with_request_user(msg.request_user):
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
    def _with_request_user(self, request_user: RequestUser) -> Generator[None, None, None]:
        env = get_qpy_environment()
        if env.request_user:
            msg = "There is already a request_user in the current environment."
            raise RuntimeError(msg)

        env.request_user = request_user
        try:
            for callback in self._on_request_callbacks:
                callback(request_user)

            yield
        finally:
            env.request_user = None


class PackageInitFailedError(Exception):
    pass


class WorkerNotInitializedError(Exception):
    pass


class MainPackageNotLoadedError(Exception):
    pass
