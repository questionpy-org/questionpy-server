#!/bin/sh
set -o errexit

cd "$(dirname "$0")"
exec npx "@stoplight/spectral-cli@^6.15.0" lint qppe-server.yaml qppe-lms.yaml
