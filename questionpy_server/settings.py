import logging
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from pydantic import BaseModel, BaseSettings
from pydantic.env_settings import InitSettingsSource, SettingsSourceCallable


class IniFileSettingsSource:
    def __init__(self, config_files: Tuple[Path, ...]):
        self.config_files = config_files

    def __call__(self, settings: BaseSettings) -> Dict[str, Any]:
        log = logging.getLogger('questionpy-server')
        for path in self.config_files:
            if not path.is_file():
                log.info("No file found at '%s'", path)
                continue
            log.info("Reading config file '%s'", path)

            parser = ConfigParser()
            parser.read(path)
            return {'webservice': dict(parser['webservice'])}

        log.fatal('No config file found!')
        return {}


class WebserviceSettings(BaseModel):
    listen_address: str = '127.0.0.1'
    listen_port: int = 9010


class Settings(BaseSettings):
    webservice: WebserviceSettings
    config_files: Tuple[Path, ...] = ()

    class Config:
        env_prefix = 'qpy_'

        @classmethod
        def customise_sources(
                cls,
                init_settings: InitSettingsSource,
                env_settings: SettingsSourceCallable,
                # pylint: disable=unused-argument
                file_secret_settings: SettingsSourceCallable
        ) -> Tuple[Callable, ...]:
            if "config_files" in init_settings.init_kwargs:
                return init_settings, IniFileSettingsSource(init_settings.init_kwargs["config_files"]), env_settings

            return init_settings, env_settings
