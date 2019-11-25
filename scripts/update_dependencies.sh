#!/bin/bash
cd "$(dirname -- "$(readlink -f "$0")")/.."

for dname in manager orchestrator; do
    echo "Updating packages for $dname"
    (cd "$dname" && pipenv update --dev)
done
