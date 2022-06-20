#!/bin/sh

printf -- 'running flake8 \n';
flake8 questionpy
flake8 tests

printf -- 'running pylint \n';
pylint questionpy
pylint tests

printf -- 'running pytest \n';
pytest tests

printf -- 'running mypy \n';
mypy questionpy
mypy tests