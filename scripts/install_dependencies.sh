#!/bin/bash
cd "$(dirname -- "$(readlink -f "$0")")/.."

for dname in manager orchestrator; do
    echo "Installing packages for $dname"
    (cd "$dname" && pipenv install --dev --deploy)
done
