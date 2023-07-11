#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

class WorkerNotRunningError(Exception):
    pass


class WorkerStartError(Exception):
    pass


class WorkerMemoryLimitExceededError(Exception):
    pass


class WorkerCPUTimeLimitExceededError(Exception):
    pass


class WorkerUnknownError(Exception):
    pass
