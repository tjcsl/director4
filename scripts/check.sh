#!/bin/sh
cd "$(dirname -- "$(dirname -- "$(readlink -f "$0")")")"

set -e

echo '=== shared ==='
(cd manager && pipenv run ../shared/scripts/check.sh)

echo '=== manager ==='
(cd manager && pipenv run ./scripts/check.sh)

echo '=== orchestrator ==='
(cd orchestrator && pipenv run ./scripts/check.sh)

echo '=== router ==='
(cd router && pipenv run ./scripts/check.sh)

echo '=== shell ==='
(cd shell && pipenv run ./scripts/check.sh)
