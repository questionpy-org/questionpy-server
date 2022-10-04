import logging
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, Optional

from pydantic import BaseModel, BaseSettings, validator
from pydantic.env_settings import InitSettingsSource, SettingsSourceCallable
from questionpy_common import constants


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
            return {key: section for key, section in parser.items() if key != 'DEFAULT'}

        log.fatal('No config file found!')
        return {}


class WebserviceSettings(BaseModel):
    listen_address: str = '127.0.0.1'
    listen_port: int = 9020
    max_bytes_client: int = 31_457_280
    max_bytes_main: int = 5_242_880
    max_bytes_package: int = constants.MAX_BYTES_PACKAGE

    @validator('max_bytes_package')
    # pylint: disable=no-self-argument
    def max_bytes_package_bigger_then_predefined_value(cls, value: int) -> int:
        if value < constants.MAX_BYTES_PACKAGE:
            raise ValueError(f'max_bytes_package must be bigger than {constants.MAX_BYTES_PACKAGE}')
        return value


class PackageCacheSettings(BaseModel):
    size: int = 104_857_600
    directory: str = 'cache/packages'


class QuestionStateCacheSettings(BaseModel):
    size: int = 20_971_520
    directory: str = 'cache/question_state'


class CollectorSettings(BaseModel):
    local_directory: Optional[str]

    @validator('local_directory')
    # pylint: disable=no-self-argument
    def transform_empty_string_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value == '':
            return None
        return value


class Settings(BaseSettings):
    webservice: WebserviceSettings
    cache_package: PackageCacheSettings
    cache_question_state: QuestionStateCacheSettings
    collector: CollectorSettings

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
