#!/bin/bash
cd "$(dirname -- "$(dirname -- "$(readlink -f "$0")")")"

if ! command -v ruff >/dev/null 2>&1; then
    echo "Could not find ruff. Run 'pipenv install --dev' to install it."
    exit 1
fi

ruff check --fix directorutil && ruff format directorutil
