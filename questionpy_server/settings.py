import logging
from configparser import ConfigParser
from datetime import timedelta
from pathlib import Path
from pydoc import locate
from typing import Any, Callable, Dict, Tuple, Optional, Type, Union, Final

from pydantic import BaseModel, BaseSettings, validator, Field, DirectoryPath, ByteSize, HttpUrl
from pydantic.env_settings import InitSettingsSource, SettingsSourceCallable
from questionpy_common.constants import MAX_PACKAGE_SIZE, MiB

from questionpy_server.worker.worker import Worker
from questionpy_server.worker.worker.subprocess import SubprocessWorker

REPOSITORY_MINIMUM_INTERVAL: Final[timedelta] = timedelta(minutes=5)


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
    type: Type[Worker] = SubprocessWorker
    """Fully qualified name of the worker class or the class itself (for the default)."""
    max_workers: int = 8
    max_memory: ByteSize = ByteSize(500 * MiB)

    @validator("type", pre=True)
    # pylint: disable=no-self-argument
    def _load_worker_class(cls, value: object) -> Type[Worker]:
        if isinstance(value, str):
            value = locate(value)

        if not isinstance(value, type) or not issubclass(value, Worker):
            raise TypeError(f"{value} is not a subclass of Worker")

        return value


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


class RepoIndexCacheSettings(BaseModel):
    size: ByteSize = ByteSize(200 * MiB)
    directory: DirectoryPath = Path('cache/repo_index').resolve()

    @validator('directory')
    # pylint: disable=no-self-argument
    def resolve_path(cls, value: Path) -> Path:
        return value.resolve()


class CollectorSettings(BaseModel):
    local_directory: Optional[DirectoryPath]
    repository_default_interval: timedelta = timedelta(hours=1, minutes=30)
    repositories: dict[HttpUrl, timedelta] = {}

    @validator('local_directory')
    # pylint: disable=no-self-argument
    def transform_to_path(cls, value: Optional[DirectoryPath]) -> Optional[DirectoryPath]:
        if value is None or value == Path(''):
            return None
        return value.resolve()

    @validator('repository_default_interval')
    # pylint: disable=no-self-argument
    def check_is_bigger_than_minimum_interval(cls, value: timedelta) -> timedelta:
        if value < REPOSITORY_MINIMUM_INTERVAL:
            raise ValueError(f"must be at least {REPOSITORY_MINIMUM_INTERVAL}")
        return value

    @validator('repositories', pre=True)
    # pylint: disable=no-self-argument
    def transform_to_set_of_repositories(cls, value: str, values: dict[str, Any]) -> dict[str, Union[str, timedelta]]:
        repositories: dict[str, Union[str, timedelta]] = {}

        for line in value.splitlines():
            if not line:
                continue

            # Split line into url and custom update interval.
            data = line.split(maxsplit=1)

            if len(data) == 1:
                url = data[0]
                custom_interval = None
            else:
                url, custom_interval = data

            if not url.endswith('/'):
                url += '/'

            if url in repositories:
                raise ValueError(f"must contain unique repositories: failed for {url}")

            # Either use the custom or default update interval.
            # If no custom interval is specified and the validation for `repository_default_interval` failed, a valid
            # interval (the minimum) is provided to ensure that the validation continues to take place.
            repositories[url] = custom_interval or values.get('repository_default_interval') or \
                REPOSITORY_MINIMUM_INTERVAL

        return repositories

    @validator('repositories')
    # pylint: disable=no-self-argument
    def check_custom_interval_is_bigger_than_minimum(cls, value: dict[HttpUrl, timedelta]) -> dict[HttpUrl, timedelta]:
        for url, custom_interval in value.items():
            if custom_interval < REPOSITORY_MINIMUM_INTERVAL:
                raise ValueError(f"update intervals must be at least {REPOSITORY_MINIMUM_INTERVAL}: failed for {url}")
        return value


class Settings(BaseSettings):
    webservice: WebserviceSettings
    worker: WorkerSettings
    cache_package: PackageCacheSettings
    cache_question_state: QuestionStateCacheSettings
    cache_repo_index: RepoIndexCacheSettings
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
