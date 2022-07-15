#!/bin/sh

printf -- 'running flake8 \n'
flake8 questionpy tests

printf -- 'running pylint \n'
pylint questionpy tests

printf -- 'running pytest \n'
pytest tests

printf -- 'running mypy \n'
mypy questionpy tests