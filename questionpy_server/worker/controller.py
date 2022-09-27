from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from questionpy_common.manifest import Manifest
from questionpy_common.elements import OptionsFormDefinition
from .worker import WorkerProcessBase, WorkerProcess, WorkerResourceLimits
from .runtime.messages import GetQPyPackageManifest, GetOptionsFormDefinition


class Worker:
    def __init__(self, process: WorkerProcessBase):
        self.process: WorkerProcessBase = process

    async def get_manifest(self) -> Manifest:
        """Get manifest of the main package in the worker."""
        msg = GetQPyPackageManifest(path=str(self.process.package))
        ret = await self.process.send_and_wait_response(msg, GetQPyPackageManifest.Response)
        return ret.manifest

    async def get_options_form_definition(self) -> OptionsFormDefinition:
        """Get the package options form definition."""
        msg = GetOptionsFormDefinition()
        ret = await self.process.send_and_wait_response(msg, GetOptionsFormDefinition.Response)
        return ret.definition


class WorkerPool:
    def __init__(self, max_workers: int, max_memory: int):
        """
        Initialize the worker pool.

        :param max_workers: maximum number of workers being executed in parallel
        :param max_memory: maximum memory (in bytes) that all workers in the pool are allowed to consume
        """
        #  TODO handle arguments

    @asynccontextmanager
    async def get_worker(self, package: Path, lms: int, context: Optional[int]) -> AsyncIterator[Worker]:
        """
        Get a (new) worker executing a QuestionPy package. A context manager is used to ensure
        that a worker is always given back to the pool.

        :param package: path to QuestionPy package
        :param lms: id of the LMS
        :param context: context id within the lms
        :return: a worker
        """
        process = None
        if context is None:
            context = 0
        try:
            example_limits = WorkerResourceLimits(max_memory_bytes=1024, max_cpu_time_seconds_per_call=10)  # TODO
            process = WorkerProcess(package, lms, context, example_limits)
            await process.start()

            worker = Worker(process)
            yield worker
        finally:
            if process:
                await process.stop(10)
