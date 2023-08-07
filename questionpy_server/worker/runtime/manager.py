#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import warnings
from pathlib import Path
from typing import TypeVar, Optional, Callable, Any

import resource

from questionpy_server.worker import WorkerResourceLimits
from questionpy_server.worker.runtime.connection import WorkerToServerConnection
from questionpy_server.worker.runtime.messages import MessageToServer, MessageIds, LoadQPyPackage, \
    GetQPyPackageManifest, GetOptionsForm, CreateQuestionFromOptions, InitWorker, Exit, WorkerError, StartAttempt, \
    ViewAttempt
from questionpy_server.worker.runtime.package import QPyPackage, QPyMainPackage

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
            GetOptionsForm.message_id: self.on_msg_get_options_form_definition,
            CreateQuestionFromOptions.message_id: self.on_msg_create_question_from_options,
            StartAttempt.message_id: self.on_msg_start_attempt,
            ViewAttempt.message_id: self.on_msg_view_attempt,
        }

    def bootstrap(self) -> None:
        init_msg = self.server_connection.receive_message()
        if not isinstance(init_msg, InitWorker):
            raise BootstrapError()

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

    def on_msg_get_options_form_definition(self, msg: GetOptionsForm) -> MessageToServer:
        if self.main_package is None:
            raise MainPackageNotLoadedError()

        definition, form_data = self.main_package.qtype_instance.get_options_form(msg.question_state)
        return GetOptionsForm.Response(definition=definition, form_data=form_data)

    def on_msg_create_question_from_options(self, msg: CreateQuestionFromOptions) -> CreateQuestionFromOptions.Response:
        if self.main_package is None:
            raise MainPackageNotLoadedError()

        question = self.main_package.qtype_instance.create_question_from_options(msg.question_state, msg.form_data)

        return CreateQuestionFromOptions.Response(question_state=question.export_question_state(),
                                                  question_model=question.export())

    def on_msg_start_attempt(self, msg: StartAttempt) -> StartAttempt.Response:
        if self.main_package is None:
            raise MainPackageNotLoadedError()

        question = self.main_package.qtype_instance.create_question_from_state(msg.question_state)
        attempt = question.start_attempt(msg.variant)
        return StartAttempt.Response(attempt_state=attempt.export_attempt_state(), attempt_model=attempt.export())

    def on_msg_view_attempt(self, msg: ViewAttempt) -> ViewAttempt.Response:
        if self.main_package is None:
            raise MainPackageNotLoadedError()

        question = self.main_package.qtype_instance.create_question_from_state(msg.question_state)
        attempt = question.view_attempt(msg.attempt_state)
        if __debug__ and msg.attempt_state != attempt.export_attempt_state():
            warnings.warn("The attempt state has been changed by viewing the attempt, which has no effect and should "
                          "not happen.")

        return ViewAttempt.Response(attempt_model=attempt.export())


class BootstrapError(Exception):
    pass


class MainPackageNotLoadedError(Exception):
    pass
