#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from collections.abc import MutableMapping
from typing import Any


class URLAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        if self.extra and "url" in self.extra:
            return f'({self.extra["url"]}): {msg}', kwargs
        return msg, kwargs
