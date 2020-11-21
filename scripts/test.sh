#!/bin/bash

# Runs test suites and prints out coverage reports for each.

cd "$(dirname -- "$(dirname -- "$(readlink -f "$0")")")"

set -e

echo '=== manager ==='
(cd manager && pipenv run coverage run --source ..,director manage.py test && pipenv run coverage report -m)

echo '=== orchestrator ==='
(cd orchestrator && pipenv run coverage run --source ..,orchestrator -m unittest discover && pipenv run coverage report --ignore-errors -m)

echo '=== router ==='
(cd router && pipenv run coverage run --source ..,router -m unittest discover && pipenv run coverage report -m)

echo '=== shell ==='
(cd shell && pipenv run coverage run --source ..,shell -m unittest discover && pipenv run coverage report -m)

