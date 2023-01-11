#!/bin/sh

printf -- 'running flake8 \n'
flake8 questionpy_server tests

printf -- 'running pylint \n'
pylint questionpy_server tests

printf -- 'running pytest \n'
coverage run -m pytest tests
coverage report

printf -- 'running mypy \n'
mypy questionpy_server tests
