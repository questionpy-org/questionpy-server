import argparse
import logging
import sys
from pathlib import Path
from . import __version__
from .app import QPyServer
from .settings import Settings

_DEFAULT_CONFIG_FILES = (
    Path('.', 'config.ini'),
    Path('/etc/questionpy-server.ini'),
)


def main() -> None:
    # Log level
    logging.basicConfig(level=logging.INFO)

    # Arguments
    parser = argparse.ArgumentParser(description=f"QuestionPy Application Server {__version__}")
    parser.add_argument('--config', help='path to config file', default=_DEFAULT_CONFIG_FILES, type=Path)
    args = parser.parse_args()

    settings = Settings(config_files=args.config)

    qpy_server = QPyServer(settings)
    qpy_server.start_server()


if __name__ == '__main__':
    main()
