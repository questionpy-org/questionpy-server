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
