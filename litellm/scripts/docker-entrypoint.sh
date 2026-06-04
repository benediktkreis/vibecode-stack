#!/bin/sh
set -e

python3 /app/scripts/generate-runtime-config.py

exec /app/docker/prod_entrypoint.sh "$@"
