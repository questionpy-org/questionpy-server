#!/bin/sh

#
# This file is part of the QuestionPy Server. (https://questionpy.org)
# The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
# (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
#

printf -- 'running flake8 \n'
flake8 questionpy_server tests

printf -- 'running pylint \n'
pylint questionpy_server tests

printf -- 'running pytest \n'
coverage run -m pytest tests
coverage report

printf -- 'running mypy \n'
mypy questionpy_server tests
