#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import logging
from configparser import ConfigParser
from datetime import timedelta
from os import environ
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic.error_wrappers import ValidationError
from pydantic.networks import HttpUrl

from questionpy_server.settings import EnvSettingsSourceWrapper, Settings


@pytest.fixture()
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
    path = tmp_path / 'config.ini'
    with path.open('w') as file:
        parser.write(file)
    return path


def test_env_settings_source_wrapper(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    env_settings_source = Mock(return_value={'test': 'value', 'nested': {'test': 'value'}})
    settings_wrapper = EnvSettingsSourceWrapper(env_settings_source)

    # Test that the wrapper calls the underlying source.
    settings = Mock()
    settings_wrapper(settings)
    env_settings_source.assert_called_once_with(settings)

    # Test logs.
    assert caplog.record_tuples[0] == ('questionpy-server:settings', logging.INFO,
                                       'Reading settings from environment variables, 2 in total. Environment variables '
                                       'overwrite settings from the config file.')

    logger_name, level, message = caplog.record_tuples[1]
    assert logger_name == 'questionpy-server:settings' and level == logging.DEBUG
    assert message.startswith('Following settings were read from environment variables: ')
    assert message.endswith("{'test: value', 'nested->test: value'}") or \
           message.endswith("{'nested->test: value', 'test: value'}")


def test_env_var_has_higher_priority_than_config_file(path_with_empty_config_file: Path) -> None:
    config = ConfigParser()
    config.read(path_with_empty_config_file)

    # Set log level to 'DEBUG' inside config.ini.
    with path_with_empty_config_file.open('w') as fp:
        config.set('general', 'log_level', 'DEBUG')
        config.write(fp)

    # Set log level environment variable to 'WARNING'.
    with patch.dict(environ, {'QPY_GENERAL__LOG_LEVEL': 'WARNING'}):
        settings = Settings(config_files=(path_with_empty_config_file,))

        assert settings.general.log_level == 'WARNING'


def test_env_var_get_validated(path_with_empty_config_file: Path) -> None:
    with patch.dict(environ, {'QPY_WEBSERVICE__LISTEN_PORT': 'invalid'}):
        with pytest.raises(ValidationError, match='webservice -> listen_port\n  value is not a valid integer'):
            Settings(config_files=(path_with_empty_config_file,))


def test_multiline_env_var_gets_parsed_correctly(path_with_empty_config_file: Path) -> None:
    with patch.dict(environ, {'QPY_COLLECTOR__REPOSITORIES': 'http://www.example.com/1\t3:30:30\n'
                                                             'http://www.example.com/2 2 7:00:00'}):
        settings = Settings(config_files=(path_with_empty_config_file, ))
        assert settings.collector.repositories == {
            HttpUrl('http://www.example.com/1/', scheme='http'): timedelta(hours=3, minutes=30, seconds=30),
            HttpUrl('http://www.example.com/2/', scheme='http'): timedelta(days=2, hours=7)
        }
