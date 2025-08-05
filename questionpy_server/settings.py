#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
import builtins
import logging
from datetime import timedelta
from pathlib import Path
from pydoc import locate
from typing import Any, ClassVar, Final, Literal

import semver
import yaml
from pydantic import BaseModel, ByteSize, DirectoryPath, HttpUrl, PositiveInt, conset, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from questionpy_common.constants import MAX_PACKAGE_SIZE, GiB, MiB
from questionpy_common.manifest import PartialWorkerPermissions, ensure_is_valid_name
from questionpy_server.worker import Worker
from questionpy_server.worker.impl.subprocess import SubprocessWorker

REPOSITORY_MINIMUM_INTERVAL: Final[timedelta] = timedelta(minutes=5)

_log = logging.getLogger("questionpy-server:settings")


class YamlFileSettingsSource(PydanticBaseSettingsSource):
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

            config = yaml.safe_load(path.read_text())
            if not isinstance(config, dict):
                _log.warning("Malformed config file '%s'! Skipping", path)
                continue

            return {title: section or {} for title, section in config.items()}

        _log.warning("No config file found!")
        return {}


class GeneralSettings(BaseModel):
    log_level: Literal["NONE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def logging_level_to_upper(cls, value: str) -> str:
        return value.upper()


class WebserviceSettings(BaseModel):
    listen_address: str = "127.0.0.1"
    listen_port: int = 9020
    allow_lms_packages: bool = True

    # Not configurable. Only here because it is analogous to max_package_size.
    max_main_size: ClassVar[ByteSize] = ByteSize(5 * MiB)

    max_package_size: ByteSize = MAX_PACKAGE_SIZE

    @field_validator("max_package_size")
    @classmethod
    def max_package_size_bigger_then_predefined_value(cls, value: ByteSize) -> ByteSize:
        if value < MAX_PACKAGE_SIZE:
            msg = f"max_package_size must be bigger than {MAX_PACKAGE_SIZE.human_readable()}"
            raise ValueError(msg)
        return value


class WorkerPoolSettings(BaseModel):
    type: builtins.type[Worker] = SubprocessWorker
    """Fully qualified name of the worker class or the class itself (for the default)."""
    max_cpus: int = 8
    max_memory: ByteSize = ByteSize(500 * MiB)

    @field_validator("type", mode="before")
    @classmethod
    def _load_worker_class(cls, value: object) -> builtins.type[Worker]:
        if isinstance(value, str):
            klass = locate(value)

            if klass is None:
                msg = f"Could not locate class '{value}'"
                raise TypeError(msg)

            value = klass

        if not isinstance(value, type) or not issubclass(value, Worker):
            msg = f"{value} is not a subclass of Worker"
            raise TypeError(msg)

        return value


class PackageOrigin(BaseModel):
    repositories: str = "*"
    local: bool | None = None
    users: str = "*"


class PackageSelector(BaseModel):
    origin: PackageOrigin = PackageOrigin()
    request_context: str = "*"
    namespace: str = "*"
    short_name: str = "*"
    version: str = "*"
    hash: str = "*"

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value == "*":
            return value
        try:
            # INFO: https://github.com/python-semver/python-semver/issues/241
            semver.Version(0).match(value)
        except ValueError as e:
            msg = f"Invalid version expression '{value}'"
            raise ValueError(msg) from e
        return value

    @field_validator("short_name", "namespace")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if value == "*":
            return value
        try:
            ensure_is_valid_name(value)
        except ValueError as e:
            msg = f"Invalid name '{value}': {e}"
            raise ValueError(msg) from e
        return value


MainProcessExecutionModeValues = {"container", "trusted"}


class SpecificWorkerPermissions(BaseModel):
    package_selector: PackageSelector = PackageSelector()
    auto_grant_permissions: PartialWorkerPermissions | None = None
    override_permissions: PartialWorkerPermissions | None = None

    @field_validator("auto_grant_permissions", "override_permissions")
    @classmethod
    def check_permissions(cls, value: PartialWorkerPermissions | None) -> PartialWorkerPermissions | None:
        if (
            value
            and value.main_process_execution_modes
            and not value.main_process_execution_modes.issubset(MainProcessExecutionModeValues)
        ):
            msg = f"'main_process_execution_modes' must be a subset of {MainProcessExecutionModeValues}"
            raise ValueError(msg)
        return value


class CompleteWorkerPermissions(BaseModel):
    cpus: int = 1
    memory: ByteSize = ByteSize(200 * MiB)
    request_timeout: PositiveInt = 10
    bootstrap_timeout: PositiveInt = 4
    main_process_execution_modes: conset(str, min_length=1) = {"container"}  # type: ignore[valid-type]

    @field_validator("main_process_execution_modes")
    @classmethod
    def check_main_process_execution_modes(cls, value: set[str]) -> set[str]:
        if not value.issubset(MainProcessExecutionModeValues):
            msg = f"must be a subset of {MainProcessExecutionModeValues}"
            raise ValueError(msg)
        return value


class WorkerPermissionsSettings(BaseModel):
    auto_grant_permissions: CompleteWorkerPermissions = CompleteWorkerPermissions()
    packages: list[SpecificWorkerPermissions] = []


class CacheSettings(BaseModel):
    size: ByteSize = ByteSize(1 * GiB)
    directory: DirectoryPath = Path("cache").resolve()

    @field_validator("directory")
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        return value.resolve()


class CollectorSettings(BaseModel):
    local_directory: DirectoryPath | None = None
    repositories: dict[HttpUrl, timedelta] = {}

    @field_validator("local_directory")
    @classmethod
    def transform_to_path(cls, value: DirectoryPath | None) -> DirectoryPath | None:
        if value is None or value == Path(""):
            return None
        return value.resolve()

    @field_validator("repositories")
    @classmethod
    def check_interval_is_bigger_than_minimum(cls, value: dict[HttpUrl, timedelta]) -> dict[HttpUrl, timedelta]:
        for url, interval in value.items():
            if interval < REPOSITORY_MINIMUM_INTERVAL:
                msg = f"update intervals must be at least {REPOSITORY_MINIMUM_INTERVAL}: failed for {url}"
                raise ValueError(msg)
        return value


class AuthSettings(BaseModel):
    enabled: bool = True
    users: dict[str, str] = {}


class CustomEnvSettingsSource(EnvSettingsSource):
    """Load settings from environment variables.

    Notify the user if any environment variables are found which overwrite the settings file.

    If the loglevel is `DEBUG` it outputs the exact variables.
    """

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)

    def _format_settings(self, settings: dict[str, Any], result: set | None = None, parent: str = "") -> set[str]:
        if result is None:
            result = set()

        for key, value in settings.items():
            if isinstance(value, dict):
                self._format_settings(value, result, f"{parent}{key}->")
            else:
                result.add(f"{parent}{key}: {value}")

        return result

    def __call__(self) -> dict[str, Any]:
        env_settings = super().__call__()
        if _log.isEnabledFor(logging.INFO) and env_settings:
            formatted_settings = self._format_settings(env_settings)
            _log.info(
                "Reading settings from environment variables, %s in total. Environment variables overwrite "
                "settings from the config file.",
                len(formatted_settings),
            )
            _log.debug("Following settings were read from environment variables: %s", sorted(formatted_settings))
        return env_settings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="qpy_", env_nested_delimiter="__")

    general: GeneralSettings
    webservice: WebserviceSettings
    worker_pool: WorkerPoolSettings
    permissions: WorkerPermissionsSettings
    cache: CacheSettings
    collector: CollectorSettings
    auth: AuthSettings

    config_files: tuple[Path, ...] = ()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if not isinstance(init_settings, InitSettingsSource):
            msg = "Expected 'init_settings' to be of type InitSettingsSource."
            raise TypeError(msg)

        if "config_files" in init_settings.init_kwargs:
            yaml_settings = YamlFileSettingsSource(settings_cls, init_settings.init_kwargs["config_files"])
            return init_settings, CustomEnvSettingsSource(settings_cls), yaml_settings

        return init_settings, env_settings
