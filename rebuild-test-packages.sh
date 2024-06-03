#!/bin/bash
#
# This file is part of the QuestionPy Server. (https://questionpy.org)
# The QuestionPy Server is free software released under terms of the MIT license. See LICENSE.md.
# (c) Technische Universität Berlin, innoCampus <info@isis.tu-berlin.de>
#

set -o nounset -o errexit

readonly SERVER_DIR="$(realpath .)"
readonly SDK_DIR="$(realpath ../questionpy-sdk)"

build_package() {
  local tmp_source_dir package
  tmp_source_dir="$(mktemp -du)"
  package="$SERVER_DIR/tests/test_data/package/$1.qpy"

  cd "$SDK_DIR"
  python -m questionpy_sdk create "$1" -o "$tmp_source_dir"
  python -m questionpy_sdk package -f "$tmp_source_dir" -o "$package"

  rm -rf "$tmp_source_dir"
}

. "$SDK_DIR/.venv/bin/activate"

build_package package_1
build_package package_2
