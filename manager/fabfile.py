import os

from fabric import task

env = {key: os.environ[key] for key in ["LANG", "PATH", "TERM", "USER", "LOGNAME", "HOME", "LS_COLORS"] if key in os.environ}

my_hosts = ["localhost"]

@task
def install(c):
    c.run("pipenv install --dev --deploy", env=env, pty=True)

@task
def runserver(c, port=8080):
    c.run("pipenv run python ./manage.py runserver 0.0.0.0:{}".format(port), env=env, pty=True)

@task
def shell(c):
    c.run("pipenv run python ./manage.py shell_plus", env=env, pty=True)

@task
def makemigrations(c):
    c.run("pipenv run python ./manage.py makemigrations", env=env, pty=True)

@task
def migrate(c):
    c.run("pipenv run python ./manage.py migrate", env=env, pty=True)
