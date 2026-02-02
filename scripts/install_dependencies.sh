#!/bin/bash
cd "$(dirname -- "$(readlink -f "$0")")/.."

if ! command -v python3.13 >/dev/null 2>&1; then
    echo "python3.13 is required but not found on PATH."
    exit 1
fi

export PIPENV_DEFAULT_PYTHON="$(command -v python3.13)"

for dname in manager orchestrator router shell; do
    echo "Installing packages for $dname"
    (cd "$dname" && pipenv install --dev --deploy)
done
