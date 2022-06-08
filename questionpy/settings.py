import logging
from configparser import ConfigParser
from pathlib import Path
from typing import Tuple, Callable, List, Dict, Optional, Any
from pydantic import BaseModel, BaseSettings
from pydantic.env_settings import SettingsSourceCallable


class WebserviceSettings(BaseModel):
    listen_address: str = '127.0.0.1'
    listen_port: int = 9010


class Settings(BaseSettings):
    webservice: WebserviceSettings
    _config_file_paths: List[Path]

    def __init__(self, config_file: Optional[Path], *args, **kwargs):
        if config_file:
            self._config_file_paths = [config_file]
        else:
            self._config_file_paths = [
                Path('.', 'config.ini'),
                Path('/etc/questionpy-server.ini'),
            ]

        super().__init__(*args, **kwargs)

    def get_config_file_paths(self) -> List[Path]:
        return self._config_file_paths

    class Config:
        env_prefix = 'qpy_'
        underscore_attrs_are_private = True

        @classmethod
        def customise_sources(
                cls,
                init_settings: SettingsSourceCallable,
                env_settings: SettingsSourceCallable,
                file_secret_settings: SettingsSourceCallable
        ) -> Tuple[Callable, ...]:
            return init_settings, ini_config_settings_source, env_settings


def ini_config_settings_source(settings: Settings) -> Dict[str, Any]:
    log = logging.getLogger('questionpy-server')
    for path in settings.get_config_file_paths():
        if not path.is_file():
            log.info(f"No file found at '{path}'")
            continue
        log.info(f"Reading config file '{path}'")

        parser = ConfigParser()
        parser.read(path)
        return {'webservice': dict(parser['webservice'])}

    log.fatal('No config file found!')
    return {}
