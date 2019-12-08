import os

from fabric import task

env = {key: os.environ[key] for key in ["LANG", "PATH", "TERM", "USER", "LOGNAME", "HOME", "LS_COLORS"] if key in os.environ}

my_hosts = ["localhost"]

@task
def install(c):
    c.run("pipenv install --dev --deploy", env=env, pty=True)

@task
def runserver(c):
    c.run("cd orchestrator; pipenv run python app.py", env=env, pty=True)
