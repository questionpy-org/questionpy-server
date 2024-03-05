#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from configparser import ConfigParser
from datetime import timedelta
from os import environ
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from pydantic.networks import HttpUrl
from pydantic_settings import EnvSettingsSource

from questionpy_server.settings import CustomEnvSettingsSource, Settings


@pytest.fixture
def path_with_empty_config_file(tmp_path: Path) -> Path:
    parser = ConfigParser()
    parser.read_string("""
        [general]
        [webservice]
        [worker]
        [cache_package]
        [cache_repo_index]
        [collector]
    """)
    path = tmp_path / "config.ini"
    with path.open("w") as file:
        parser.write(file)
    return path


def test_env_settings_source_wrapper(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    settings_wrapper = CustomEnvSettingsSource(MagicMock())

    with patch.object(
        EnvSettingsSource, "__call__", return_value={"test": "value", "nested": {"test": "value"}}
    ) as mock:
        # Test that the wrapper calls the underlying source.
        settings_wrapper()
        mock.assert_called_once_with()

    # Test logs.
    assert caplog.record_tuples[0] == (
        "questionpy-server:settings",
        logging.INFO,
        "Reading settings from environment variables, 2 in total. Environment variables "
        "overwrite settings from the config file.",
    )

    logger_name, level, message = caplog.record_tuples[1]
    assert logger_name == "questionpy-server:settings"
    assert level == logging.DEBUG
    assert message.startswith("Following settings were read from environment variables: ")
    assert message.endswith(("{'test: value', 'nested->test: value'}", "{'nested->test: value', 'test: value'}"))


# pylint: disable=redefined-outer-name
def test_env_var_has_higher_priority_than_config_file(path_with_empty_config_file: Path) -> None:
    config = ConfigParser()
    config.read(path_with_empty_config_file)

    # Set log level to 'DEBUG' inside config.ini.
    with path_with_empty_config_file.open("w") as file:
        config.set("general", "log_level", "DEBUG")
        config.write(file)

    # Set log level environment variable to 'WARNING'.
    with patch.dict(environ, {"QPY_GENERAL__LOG_LEVEL": "WARNING"}):
        settings = Settings(config_files=(path_with_empty_config_file,))

        assert settings.general.log_level == "WARNING"


# pylint: disable=redefined-outer-name
def test_env_var_get_validated(path_with_empty_config_file: Path) -> None:
    with patch.dict(environ, {"QPY_WEBSERVICE__LISTEN_PORT": "invalid"}), pytest.raises(
        ValidationError, match=r"webservice.listen_port\s*[type=int_parsing, input_value='invalid', input_type=str]"
    ):
        Settings(config_files=(path_with_empty_config_file,))


# pylint: disable=redefined-outer-name
def test_multiline_env_var_gets_parsed_correctly(path_with_empty_config_file: Path) -> None:
    with patch.dict(
        environ,
        {"QPY_COLLECTOR__REPOSITORIES": "http://www.example.com/1\t03:30:30\n" "http://www.example.com/2 2d, 07:00:00"},
    ):
        settings = Settings(config_files=(path_with_empty_config_file,))
        assert settings.collector.repositories == {
            HttpUrl("http://www.example.com/1/"): timedelta(hours=3, minutes=30, seconds=30),
            HttpUrl("http://www.example.com/2/"): timedelta(days=2, hours=7),
        }
