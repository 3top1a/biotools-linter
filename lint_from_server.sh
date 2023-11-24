#!/usr/bin/env bash
# This script exists to ensure python is correctly configured


if [ -f "env/bin/activate" ]
then
    source env/bin/activate
fi

if [ -f "venv/bin/activate" ]
then
    source env/bin/activate
fi

if [ -f ".env" ]
then
    source env/bin/activate
fi

python3 linter/cli.py $@
