# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os

from fabric import task

env = {key: os.environ[key] for key in ["LANG", "PATH", "TERM", "USER", "LOGNAME", "HOME", "LS_COLORS"] if key in os.environ}

my_hosts = ["localhost"]

@task
def install(c):
    """Install development dependencies."""
    c.run("pipenv install --dev --deploy", env=env, pty=True)

@task
def runserver(c):
    """Run development principal orchestrator server."""
    c.run("pipenv run python -m orchestrator.app", env=env, pty=True)

@task
def wsserver(c):
    """Run development WebSocket orchestrator server."""
    c.run("pipenv run python -m orchestrator.ws", env=env, pty=True)
