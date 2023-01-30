import logging
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, Optional

from questionpy_common.constants import MAX_PACKAGE_SIZE, MiB

from pydantic import BaseModel, BaseSettings, validator, Field, DirectoryPath, ByteSize
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
            return {key: section for key, section in parser.items() if key != 'DEFAULT'}

        log.fatal('No config file found!')
        return {}


class WebserviceSettings(BaseModel):
    listen_address: str = '127.0.0.1'
    listen_port: int = 9020
    max_main_size: ByteSize = Field(ByteSize(5 * MiB), const=True)
    max_package_size: ByteSize = MAX_PACKAGE_SIZE

    @validator('max_package_size')
    # pylint: disable=no-self-argument
    def max_package_size_bigger_then_predefined_value(cls, value: ByteSize) -> ByteSize:
        if value < MAX_PACKAGE_SIZE:
            raise ValueError(f'max_package_size must be bigger than {MAX_PACKAGE_SIZE.human_readable()}')
        return value


class WorkerSettings(BaseModel):
    max_workers: int = 8
    max_memory: ByteSize = ByteSize(500 * MiB)


class PackageCacheSettings(BaseModel):
    size: ByteSize = ByteSize(5 * MiB)
    directory: DirectoryPath = Path('cache/packages').resolve()

    @validator('directory')
    # pylint: disable=no-self-argument
    def resolve_path(cls, value: Path) -> Path:
        return value.resolve()


class QuestionStateCacheSettings(BaseModel):
    size: ByteSize = ByteSize(20 * MiB)
    directory: DirectoryPath = Path('cache/question_state').resolve()

    @validator('directory')
    # pylint: disable=no-self-argument
    def resolve_path(cls, value: Path) -> Path:
        return value.resolve()


class CollectorSettings(BaseModel):
    local_directory: Optional[DirectoryPath]

    @validator('local_directory')
    # pylint: disable=no-self-argument
    def transform_to_path(cls, value: Optional[DirectoryPath]) -> Optional[DirectoryPath]:
        if value is None or value == Path(''):
            return None
        return value.resolve()


class Settings(BaseSettings):
    webservice: WebserviceSettings
    worker: WorkerSettings
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
