#!/bin/bash

set -euo pipefail

script_path=$(readlink -f "$0")
repo_dir=$(dirname -- "$script_path")/..
cd "$repo_dir"

if ! command -v python3.13 >/dev/null 2>&1; then
    echo "python3.13 is required but not found on PATH."
    exit 1
fi

if ! command -v pipenv >/dev/null 2>&1; then
    echo "pipenv is required but not found on PATH."
    exit 1
fi

export PIPENV_DEFAULT_PYTHON
PIPENV_DEFAULT_PYTHON=$(command -v python3.13)
export PIPENV_NOSPIN=1

components=(manager orchestrator router shell)
marker_dir=${DIRECTOR4_DEPENDENCY_MARKER_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/director4/dependencies}
mkdir -p "$marker_dir"

dependency_jobs=${DIRECTOR4_DEPENDENCY_JOBS:-$(nproc)}
if [[ ! $dependency_jobs =~ ^[1-9][0-9]*$ ]]; then
    echo "DIRECTOR4_DEPENDENCY_JOBS must be a positive integer."
    exit 1
fi
if (( dependency_jobs > ${#components[@]} )); then
    dependency_jobs=${#components[@]}
fi

install_component() {
    local dname=$1
    local marker_file="$marker_dir/$dname.sha256"
    local fingerprint
    local venv_path

    fingerprint=$(
        {
            sha256sum "$script_path" "$dname/Pipfile" "$dname/Pipfile.lock"
            "$PIPENV_DEFAULT_PYTHON" --version
            pipenv --version
        } | sha256sum | awk '{print $1}'
    )

    venv_path=$(cd "$dname" && pipenv --venv 2>/dev/null || true)
    if [[ -n $venv_path ]] \
        && [[ -x "$venv_path/bin/python" ]] \
        && [[ -f "$marker_file" ]] \
        && grep -Fxq "$fingerprint" "$marker_file"; then
        echo "Skipping packages for $dname (lockfiles unchanged)"
        return 0
    fi

    echo "Installing packages for $dname"
    (cd "$dname" && pipenv install --dev --deploy)

    printf '%s\n' "$fingerprint" >"$marker_file.tmp.$$"
    mv "$marker_file.tmp.$$" "$marker_file"
}

batch_pids=()
batch_names=()

wait_for_batch() {
    local failed=0
    local index

    for index in "${!batch_pids[@]}"; do
        if ! wait "${batch_pids[$index]}"; then
            echo "Dependency installation failed for ${batch_names[$index]}."
            failed=1
        fi
    done

    batch_pids=()
    batch_names=()
    return "$failed"
}

for dname in "${components[@]}"; do
    install_component "$dname" &
    batch_pids+=("$!")
    batch_names+=("$dname")

    if (( ${#batch_pids[@]} >= dependency_jobs )); then
        wait_for_batch
    fi
done

if (( ${#batch_pids[@]} > 0 )); then
    wait_for_batch
fi
