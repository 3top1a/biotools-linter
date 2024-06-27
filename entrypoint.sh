#!/bin/bash

set -e

if [ "$1" = 'lint' ]; then
    # Run the linter
    shift 1
    exec python3 linter/cli.py "$@"
elif [ "$1" = 'server' ]; then
    # Run the server
    shift 1
    exec server --port 8080 --stats "$@"
else
    exec "$@"
fi
