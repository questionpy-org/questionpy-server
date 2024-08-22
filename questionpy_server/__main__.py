#  This file is part of the QuestionPy Server. (https://questionpy.org)
#  The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
#  (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>

import argparse
import logging
import os
from pathlib import Path

from questionpy_server.web.app import QPyServer

from . import __version__
from .settings import Settings

_DEFAULT_CONFIG_FILES = (
    Path(".", "config.ini"),
    Path("/etc/questionpy-server.ini"),
)


def update_logging(level: str) -> None:
    if level == "NONE":
        logging.disable()
    elif level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        logging.getLogger().setLevel(level)


def main() -> None:
    # Initialize logging here because we also log things while reading the settings
    logging.basicConfig()
    if log_level := os.getenv("QPY_GENERAL__LOG_LEVEL", "INFO"):
        update_logging(log_level)

    # Arguments
    parser = argparse.ArgumentParser(description=f"QuestionPy Application Server {__version__}")
    parser.add_argument("--config", help="path to config file", default=_DEFAULT_CONFIG_FILES, type=Path)
    args = parser.parse_args()

    settings = Settings(config_files=args.config)
    update_logging(settings.general.log_level)

    qpy_server = QPyServer(settings)
    qpy_server.start_server()


if __name__ == "__main__":
    main()
