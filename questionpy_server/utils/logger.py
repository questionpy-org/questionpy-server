import logging
from typing import MutableMapping, Any


class URLAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        if self.extra and 'url' in self.extra:
            return f'({self.extra["url"]}): {msg}', kwargs
        return msg, kwargs
