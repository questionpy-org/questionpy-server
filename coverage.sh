#!/bin/sh

printf -- 'running flake8 \n'
flake8 questionpy_server tests

printf -- 'running pylint \n'
pylint tests questionpy_server

printf -- 'running pytest \n'
coverage run -m pytest tests
coverage report

printf -- 'running mypy \n'
mypy questionpy_server tests
