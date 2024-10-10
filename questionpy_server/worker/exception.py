#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from questionpy_common.error import TemporaryException


class WorkerNotRunningError(TemporaryException):
    pass


class WorkerStartError(TemporaryException):
    pass


class WorkerCPUTimeLimitExceededError(TemporaryException):
    pass


class StaticFileSizeMismatchError(TemporaryException):
    pass
