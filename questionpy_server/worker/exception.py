#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from questionpy_common.error import QPyBaseError
from questionpy_server.worker.runtime.messages import BaseWorkerError


class WorkerStoppedError(BaseWorkerError):
    """Represents an error that results in or was caused by a worker being stopped."""


class WorkerStartError(BaseWorkerError):
    pass


class WorkerNotRunningError(WorkerStoppedError):
    pass


class WorkerCPUTimeLimitExceededError(WorkerStoppedError):
    def __init__(self, limit: float, worker_name: str):
        self.limit = limit
        super().__init__(
            f"Worker has exceeded its CPU time limit of {limit} seconds and was killed.", worker_name=worker_name
        )


class WorkerRealTimeLimitExceededError(WorkerStoppedError):
    def __init__(self, limit: float, worker_name: str):
        self.limit = limit
        super().__init__(
            f"Worker has exceeded its real time limit of {limit} seconds and was killed.", worker_name=worker_name
        )


class StaticFileSizeMismatchError(QPyBaseError):
    pass
