#!/bin/bash
set -o nounset -o errexit

readonly SERVER_DIR="$(realpath .)"
readonly SDK_DIR="$(realpath ../questionpy-sdk)"

build_package() {
  local tmp_source_dir package
  tmp_source_dir="$(mktemp -du)"
  package="$SERVER_DIR/tests/test_data/package/$1.qpy"

  cd "$SDK_DIR"
  python -m questionpy_sdk create "$1" -o "$tmp_source_dir"
  python -m questionpy_sdk package "$tmp_source_dir" -o "$package"

  rm -rf "$tmp_source_dir"
}

. "$SDK_DIR/.venv/bin/activate"

build_package package_1
build_package package_2
