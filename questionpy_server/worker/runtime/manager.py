#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Callable, Union, Literal, Any, Generator

import resource
from questionpy_common.environment import Environment, RequestUser, WorkerResourceLimits, OnRequestCallback, \
    get_qpy_environment
from questionpy_common.qtype import BaseQuestionType

from questionpy_server.worker.runtime.connection import WorkerToServerConnection
from questionpy_server.worker.runtime.messages import MessageToServer, MessageIds, LoadQPyPackage, \
    GetQPyPackageManifest, GetOptionsForm, CreateQuestionFromOptions, InitWorker, Exit, WorkerError, StartAttempt, \
    ViewAttempt, MessageToWorker
from questionpy_server.worker.runtime.package import ImportablePackage, load_package


@dataclass
class EnvironmentImpl(Environment):
    type: Union[Literal["process", "thread", "container"], str]
    main_package: ImportablePackage
    packages: dict[str, ImportablePackage]
    _on_request_callbacks: list[OnRequestCallback]
    request_user: Optional[RequestUser] = None
    limits: Optional[WorkerResourceLimits] = None

    def register_on_request_callback(self, callback: OnRequestCallback) -> None:
        self._on_request_callbacks.append(callback)


class WorkerManager:
    def __init__(self, server_connection: WorkerToServerConnection):
        self.worker_type: Optional[str] = None
        self.server_connection: WorkerToServerConnection = server_connection
        self.limits: Optional[WorkerResourceLimits] = None
        self.loaded_packages: dict[str, ImportablePackage] = {}
        self.main_package: Optional[ImportablePackage] = None
        self.question_type: Optional[BaseQuestionType] = None
        self.message_dispatch: dict[MessageIds, Callable[[Any], MessageToServer]] = {
            LoadQPyPackage.message_id: self.on_msg_load_qpy_package,
            GetQPyPackageManifest.message_id: self.on_msg_get_qpy_package_manifest,
            GetOptionsForm.message_id: self.on_msg_get_options_form_definition,
            CreateQuestionFromOptions.message_id: self.on_msg_create_question_from_options,
            StartAttempt.message_id: self.on_msg_start_attempt,
            ViewAttempt.message_id: self.on_msg_view_attempt,
        }
        self._on_request_callbacks: list[OnRequestCallback] = []

    def bootstrap(self) -> None:
        init_msg = self.server_connection.receive_message()
        if not isinstance(init_msg, InitWorker):
            raise WorkerNotInitializedError(f"'{InitWorker.__name__}' message expected, "
                                            f"'{type(init_msg).__name__}' received")

        self.worker_type = init_msg.worker_type
        self.limits = init_msg.limits
        if self.limits:
            # Limit memory usage.
            resource.setrlimit(resource.RLIMIT_AS, (self.limits.max_memory, self.limits.max_memory))

        self.server_connection.send_message(InitWorker.Response())

    def loop(self) -> None:
        """Dispatch incoming messages."""
        while True:
            msg = self.server_connection.receive_message()
            if isinstance(msg, Exit):
                return

            try:
                response = self.message_dispatch[msg.message_id](msg)
            except Exception as error:  # pylint: disable=broad-except
                response = WorkerError.from_exception(error, cause=msg)
            self.server_connection.send_message(response)

    def on_msg_load_qpy_package(self, msg: LoadQPyPackage) -> MessageToServer:
        self._require_init(msg)
        assert self.worker_type

        package = load_package(msg.location)
        package.setup_imports()
        self.loaded_packages[str(msg.location)] = package

        if msg.main:
            qtype = package.init_as_main(EnvironmentImpl(
                type=self.worker_type,
                limits=self.limits,
                packages=self.loaded_packages,
                main_package=package,
                _on_request_callbacks=self._on_request_callbacks
            ))
            if not isinstance(qtype, BaseQuestionType):
                raise PackageInitFailedError(f"Package initialization returned '{qtype}', BaseQuestionType expected")

            self.main_package = package
            self.question_type = qtype

        return LoadQPyPackage.Response()

    def on_msg_get_qpy_package_manifest(self, msg: GetQPyPackageManifest) -> MessageToServer:
        self._require_init(msg)

        package = self.loaded_packages[msg.path]
        return GetQPyPackageManifest.Response(manifest=package.manifest)

    def on_msg_get_options_form_definition(self, msg: GetOptionsForm) -> MessageToServer:
        self._require_init(msg)
        self._require_main_package_loaded(msg)
        assert self.question_type

        with self._with_request_user(msg.request_user):
            definition, form_data = self.question_type.get_options_form(msg.question_state)

            return GetOptionsForm.Response(definition=definition, form_data=form_data)

    def on_msg_create_question_from_options(self, msg: CreateQuestionFromOptions) -> CreateQuestionFromOptions.Response:
        self._require_init(msg)
        self._require_main_package_loaded(msg)
        assert self.question_type

        with self._with_request_user(msg.request_user):
            question = self.question_type.create_question_from_options(msg.question_state, msg.form_data)

            return CreateQuestionFromOptions.Response(question_state=question.export_question_state(),
                                                      question_model=question.export())

    def on_msg_start_attempt(self, msg: StartAttempt) -> StartAttempt.Response:
        self._require_init(msg)
        self._require_main_package_loaded(msg)
        assert self.question_type

        with self._with_request_user(msg.request_user):
            question = self.question_type.create_question_from_state(msg.question_state)
            attempt = question.start_attempt(msg.variant)
            return StartAttempt.Response(attempt_state=attempt.export_attempt_state(), attempt_model=attempt.export())

    def on_msg_view_attempt(self, msg: ViewAttempt) -> ViewAttempt.Response:
        self._require_init(msg)
        self._require_main_package_loaded(msg)
        assert self.question_type

        with self._with_request_user(msg.request_user):
            question = self.question_type.create_question_from_state(msg.question_state)
            attempt = question.view_attempt(msg.attempt_state)
            if __debug__ and msg.attempt_state != attempt.export_attempt_state():
                warnings.warn("The attempt state has been changed by viewing the attempt, which has no effect and "
                              "should not happen.")

            return ViewAttempt.Response(attempt_model=attempt.export())

    def _require_init(self, msg: MessageToWorker) -> None:
        if not self.worker_type:
            raise WorkerNotInitializedError(f"'{InitWorker.__name__}' message expected, "
                                            f"'{type(msg).__name__}' received")

    def _require_main_package_loaded(self, msg: MessageToWorker) -> None:
        if not (self.main_package and self.loaded_packages and self.question_type):
            raise MainPackageNotLoadedError(f"'{LoadQPyPackage.__name__}(main=True)' message expected, "
                                            f"'{type(msg).__name__}' received")

    @contextmanager
    def _with_request_user(self, request_user: RequestUser) -> Generator[None, None, None]:
        env = get_qpy_environment()
        if env.request_user:
            raise RuntimeError("There is already a request_user in the current environment.")

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
