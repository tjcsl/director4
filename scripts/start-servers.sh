#!/bin/bash
cd "$(dirname -- "$(readlink -f "$0")")/.."

tmux new-session -s servers -c manager \
    "expect ../scripts/launch-and-interact.exp 'fab runserver'" ';' \
    split-window -p 80 -c manager "expect ../scripts/launch-and-interact.exp 'fab celery'" ';' \
    split-window -p 75 -c orchestrator "expect ../scripts/launch-and-interact.exp 'fab runserver'" ';' \
    split-window -p 67 -c orchestrator "expect ../scripts/launch-and-interact.exp 'fab wsserver'" ';' \
    split-window -p 50 -c shell "expect ../scripts/launch-and-interact.exp 'fab server'"
