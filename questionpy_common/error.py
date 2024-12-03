#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from typing import Any


class QPyBaseError(Exception):
    """QuestionPy errors should inherit this class as the webserver transforms these into better http errors.

    Args:
        args: Any other arguments.
        reason: A human-readable reason which can be exposed to a third party.
        temporary: Whether this exception is temporary.
    """

    def __init__(self, *args: Any, reason: str | None = None, temporary: bool = False):
        super().__init__(*args)
        self.temporary = temporary
        self.reason = reason
