#!/bin/sh

printf -- 'running flake8 \n'
flake8 questionpy_common tests

printf -- 'running pylint \n'
pylint questionpy_common tests

printf -- 'running pytest \n'
coverage run -m pytest tests
coverage report

printf -- 'running mypy \n'
mypy questionpy_common tests
