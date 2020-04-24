#!/bin/sh
cd "$(dirname -- "$(dirname -- "$(readlink -f "$0")")")"

set -e

echo '=== shared ==='
(cd manager && pipenv run ../shared/scripts/format.sh)

echo '=== manager ==='
(cd manager && pipenv run ./scripts/format.sh)
(cd manager && pipenv run ./scripts/static_templates_format.sh)

echo '=== orchestrator ==='
(cd orchestrator && pipenv run ./scripts/format.sh)

echo '=== router ==='
(cd router && pipenv run ./scripts/format.sh)

echo '=== shell ==='
(cd shell && pipenv run ./scripts/format.sh)
