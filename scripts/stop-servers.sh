#!/bin/bash
cd "$(dirname -- "$(readlink -f "$0")")/.."

tmux kill-session -t servers
