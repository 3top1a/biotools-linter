#!/usr/bin/env bash
# This script exists to ensure python is correctly configured

source env/bin/activate

python3 linter/cli.py $@
