from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class WorkerResourceLimits:
    """Maximum resources that a worker process is allowed to consume."""
    max_memory: int
    max_cpu_time_seconds_per_call: float


class WorkerResources(BaseModel):
    """Current resource usage."""
    memory: int
    cpu_time_since_last_call: float
    total_cpu_time: float
