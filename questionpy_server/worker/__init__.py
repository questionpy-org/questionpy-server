#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

from pydantic import BaseModel


class WorkerResources(BaseModel):
    """Current resource usage."""
    memory: int
    cpu_time_since_last_call: float
    total_cpu_time: float
