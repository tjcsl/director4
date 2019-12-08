import os

from fabric import task

env = {key: os.environ[key] for key in ["LANG", "PATH", "TERM", "USER", "LOGNAME", "HOME", "LS_COLORS"] if key in os.environ}

my_hosts = ["localhost"]

@task
def install(c):
    c.run("pipenv install --dev --deploy", env=env, pty=True)

@task
def runserver(c):
    c.run("pipenv run python -m orchestrator.app", env=env, pty=True)
