#!/bin/sh
set -e

ENV_FILE="${ENV_FILE:-/app/.env}"

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from $ENV_FILE"

    set -a
    . "$ENV_FILE"
    set +a
else
    echo "No env file found at $ENV_FILE"
fi

exec "$@"