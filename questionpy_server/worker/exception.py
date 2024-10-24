#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from questionpy_common.error import QPyBaseError
from questionpy_server.worker.runtime.messages import BaseWorkerError


class WorkerNotRunningError(BaseWorkerError):
    pass


class WorkerStartError(BaseWorkerError):
    pass


class WorkerCPUTimeLimitExceededError(BaseWorkerError):
    def __init__(self, limit: float):
        self.limit = limit
        super().__init__(f"Worker has exceeded its CPU time limit of {limit} seconds and was killed.")


class WorkerRealTimeLimitExceededError(BaseWorkerError):
    def __init__(self, limit: float):
        self.limit = limit
        super().__init__(f"Worker has exceeded its real time limit of {limit} seconds and was killed.")


class StaticFileSizeMismatchError(QPyBaseError):
    pass
