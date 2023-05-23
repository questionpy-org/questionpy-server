import argparse
import logging
import os
from pathlib import Path

from . import __version__
from .app import QPyServer
from .settings import Settings

_DEFAULT_CONFIG_FILES = (
    Path('.', 'config.ini'),
    Path('/etc/questionpy-server.ini'),
)


def update_logging(level: str) -> None:
    if level == 'NONE':
        logging.disable()
    elif level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        logging.getLogger().setLevel(level)


def main() -> None:
    # Initialize logging here because we also log things while reading the settings
    logging.basicConfig()
    if log_level := os.getenv('QPY_GENERAL__LOG_LEVEL', 'INFO'):
        update_logging(log_level)

    # Arguments
    parser = argparse.ArgumentParser(description=f"QuestionPy Application Server {__version__}")
    parser.add_argument('--config', help='path to config file', default=_DEFAULT_CONFIG_FILES, type=Path)
    args = parser.parse_args()

    settings = Settings(config_files=args.config)
    update_logging(settings.general.log_level)

    qpy_server = QPyServer(settings)
    qpy_server.start_server()


if __name__ == '__main__':
    main()
