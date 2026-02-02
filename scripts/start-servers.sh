#!/bin/bash
cd "$(dirname -- "$(readlink -f "$0")")/.."

cols=$(tput cols 2>/dev/null || true)
lines=$(tput lines 2>/dev/null || true)
: "${cols:=160}"
: "${lines:=40}"

if tmux has-session -t servers 2>/dev/null; then
    tmux attach -t servers
    exit 0
fi

tmux set-option -g default-size "${cols}x${lines}"
tmux new-session -d -s servers -c manager -x "$cols" -y "$lines" \
    "expect ../scripts/launch-and-interact.exp 'fab runserver'"

tmux set-option -t servers remain-on-exit on

tmux new-window -t servers:1 -c manager \
    "expect ../scripts/launch-and-interact.exp 'fab celery'"
tmux new-window -t servers:2 -c orchestrator \
    "expect ../scripts/launch-and-interact.exp 'fab runserver'"
tmux new-window -t servers:3 -c orchestrator \
    "expect ../scripts/launch-and-interact.exp 'fab wsserver'"
tmux new-window -t servers:4 -c shell \
    "expect ../scripts/launch-and-interact.exp 'fab server'"

tmux attach -t servers
