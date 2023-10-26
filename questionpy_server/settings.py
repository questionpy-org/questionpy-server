#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from configparser import ConfigParser
from datetime import timedelta
from pathlib import Path
from pydoc import locate
from typing import Any, Optional, Type, Literal, Union, Final, ClassVar

from pydantic import field_validator, BaseModel, DirectoryPath, ByteSize, HttpUrl, ValidationInfo
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, InitSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource, \
    SettingsConfigDict
from questionpy_common.constants import MAX_PACKAGE_SIZE, MiB

from questionpy_server.worker.worker import Worker
from questionpy_server.worker.worker.subprocess import SubprocessWorker

REPOSITORY_MINIMUM_INTERVAL: Final[timedelta] = timedelta(minutes=5)

_log = logging.getLogger('questionpy-server:settings')


class IniFileSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings], config_files: tuple[Path, ...]):
        super().__init__(settings_cls)
        self._config_files = config_files

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        # This method is abstract in PydanticBaseSettingsSource, but only ever called from
        # PydanticBaseEnvSettingsSource, which we aren't.
        return None, "", False

    def __call__(self) -> dict[str, Any]:
        for path in self._config_files:
            if not path.is_file():
                _log.info("No file found at '%s'", path)
                continue
            _log.info("Reading config file '%s'", path)

            parser = ConfigParser()
            parser.read(path)
            return {key: dict(section) for key, section in parser.items() if key != 'DEFAULT'}

        _log.warning('No config file found!')
        return {}


class GeneralSettings(BaseModel):
    log_level: Literal['NONE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'

    @field_validator('log_level', mode="before")
    @classmethod
    def logging_level_to_upper(cls, value: str) -> str:
        return value.upper()


class WebserviceSettings(BaseModel):
    listen_address: str = '127.0.0.1'
    listen_port: int = 9020

    # Not configurable. Only here because it is analogous to max_package_size.
    max_main_size: ClassVar[ByteSize] = ByteSize(5 * MiB)

    max_package_size: ByteSize = MAX_PACKAGE_SIZE

    @field_validator('max_package_size')
    @classmethod
    def max_package_size_bigger_then_predefined_value(cls, value: ByteSize) -> ByteSize:
        if value < MAX_PACKAGE_SIZE:
            raise ValueError(f'max_package_size must be bigger than {MAX_PACKAGE_SIZE.human_readable()}')
        return value


class WorkerSettings(BaseModel):
    type: Type[Worker] = SubprocessWorker
    """Fully qualified name of the worker class or the class itself (for the default)."""
    max_workers: int = 8
    max_memory: ByteSize = ByteSize(500 * MiB)

    @field_validator("type", mode="before")
    @classmethod
    def _load_worker_class(cls, value: object) -> Type[Worker]:
        if isinstance(value, str):
            value = locate(value)

        if not isinstance(value, type) or not issubclass(value, Worker):
            raise TypeError(f"{value} is not a subclass of Worker")

        return value


class PackageCacheSettings(BaseModel):
    size: ByteSize = ByteSize(5 * MiB)
    directory: DirectoryPath = Path('cache/packages').resolve()

    @field_validator('directory')
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        return value.resolve()


class RepoIndexCacheSettings(BaseModel):
    size: ByteSize = ByteSize(200 * MiB)
    directory: DirectoryPath = Path('cache/repo_index').resolve()

    @field_validator('directory')
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        return value.resolve()


class CollectorSettings(BaseModel):
    local_directory: Optional[DirectoryPath] = None
    repository_default_interval: timedelta = timedelta(hours=1, minutes=30)
    repositories: dict[HttpUrl, timedelta] = {}

    @field_validator('local_directory')
    @classmethod
    def transform_to_path(cls, value: Optional[DirectoryPath]) -> Optional[DirectoryPath]:
        if value is None or value == Path(''):
            return None
        return value.resolve()

    @field_validator('repository_default_interval')
    @classmethod
    def check_is_bigger_than_minimum_interval(cls, value: timedelta) -> timedelta:
        if value < REPOSITORY_MINIMUM_INTERVAL:
            raise ValueError(f"must be at least {REPOSITORY_MINIMUM_INTERVAL}")
        return value

    @field_validator('repositories', mode="before")
    @classmethod
    def transform_to_set_of_repositories(cls, value: str,
                                         info: ValidationInfo) -> dict[str, Union[str, timedelta]]:
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
            repositories[url] = custom_interval \
                or info.data.get('repository_default_interval') \
                or REPOSITORY_MINIMUM_INTERVAL

        return repositories

    @field_validator('repositories')
    @classmethod
    def check_custom_interval_is_bigger_than_minimum(cls, value: dict[HttpUrl, timedelta]) -> dict[HttpUrl, timedelta]:
        for url, custom_interval in value.items():
            if custom_interval < REPOSITORY_MINIMUM_INTERVAL:
                raise ValueError(f"update intervals must be at least {REPOSITORY_MINIMUM_INTERVAL}: failed for {url}")
        return value


class CustomEnvSettingsSource(EnvSettingsSource):
    """
    Loads settings from environment variables and notifies the user if any environment variables are found which
    overwrite the settings file.

    pydantic-settings v2 tries to parse multi-line ('complex') environment variables as JSON. This subclass overrides
    that behaviour.

    If the loglevel is `DEBUG` it outputs the exact variables.
    """

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)

    def _get_settings(self, settings: dict[str, Any], result: Optional[set] = None, parent: str = '') -> set[str]:
        if result is None:
            result = set()

        for key, value in settings.items():
            if isinstance(value, dict):
                self._get_settings(value, result, f'{parent}{key}->')
            else:
                result.add(f'{parent}{key}: {value}')

        return result

    def decode_complex_value(self, field_name: str, field: FieldInfo, value: Any) -> Any:
        # pydantic-settings v2 tries to parse multi-line ('complex') environment variables as JSON, which we don't want,
        # so we override it with a no-op.
        return value

    def __call__(self) -> dict[str, Any]:
        env_settings = super().__call__()
        if env_settings:
            _log.info("Reading settings from environment variables, %s in total. Environment variables overwrite "
                      "settings from the config file.", len(env_settings))
            _log.debug("Following settings were read from environment variables: %s", self._get_settings(env_settings))
        return env_settings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='qpy_', env_nested_delimiter='__')

    general: GeneralSettings
    webservice: WebserviceSettings
    worker: WorkerSettings
    cache_package: PackageCacheSettings
    cache_repo_index: RepoIndexCacheSettings
    collector: CollectorSettings

    config_files: tuple[Path, ...] = ()

    @classmethod
    # pylint: disable=too-many-arguments
    def settings_customise_sources(
            cls, settings_cls: Type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        assert isinstance(init_settings, InitSettingsSource)
        if "config_files" in init_settings.init_kwargs:
            ini_settings = IniFileSettingsSource(settings_cls, init_settings.init_kwargs["config_files"])
            return init_settings, CustomEnvSettingsSource(settings_cls), ini_settings

        return init_settings, env_settings
