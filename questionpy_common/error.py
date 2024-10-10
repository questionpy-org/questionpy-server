#  This file is part of QuestionPy. (https://questionpy.org)
#  QuestionPy is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
from typing import Any


class TemporaryException(Exception):
    def __init__(self, *args: Any, temporary: bool):
        super().__init__(*args)
        self._temporary = temporary

    @property
    def temporary(self) -> bool:
        return self._temporary
