# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from flask import Flask, request

from . import settings
from .views.sites.docker import docker_blueprint
from .views.sites.files import files as files_blueprint
from .views.sites.nginx import nginx as nginx_blueprint

app = Flask(__name__)
app.register_blueprint(docker_blueprint)
app.register_blueprint(files_blueprint)
app.register_blueprint(nginx_blueprint)

app.config.update(settings.FLASK_CONFIG)


@app.route("/ping")
def ping_page() -> str:
    """Checks whether the orchestrator is functional.

    Returns a provided message or else "Pong".
    """

    return request.args.get("message", "Pong")


if __name__ == "__main__":
    app.run()
