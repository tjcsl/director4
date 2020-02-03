# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

# import logging
import json
import traceback

from flask import Flask, request  # , jsonify, redirect, url_for

from .configs.nginx import update_nginx_config
from .docker.services import update_director_service
from .docker.utils import create_client
from .files import ensure_site_directories_exist

app = Flask(__name__)


@app.route("/")
def index_page():
    """Returns the index page."""
    return "Hello World!!"


@app.route("/ping")
def ping_page():
    """Checks whether the orchestrator is functional.

    Returns a provided message or else "Pong".
    """

    return "{}\n".format(request.args.get("message", "Pong"))


@app.route("/sites/<int:site_id>/update-docker-service", methods=["POST"])
def update_docker_service_page(site_id: int):
    """Updates the Docker service for a given site.

    Based on the provided site_id and data, updates
    the Docker service to reflect the site's new state.
    Returns "Success" if successful, else an appropriate
    error.
    """

    if "data" not in request.form:
        return "Error", 400

    try:
        ensure_site_directories_exist(site_id)

        update_director_service(create_client(), site_id, json.loads(request.form["data"]))
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/<int:site_id>/update-nginx", methods=["POST"])
def update_nginx_page(site_id: int):
    """Updates the Nginx config for a given site.

    Based on the provided site_id and data, updates
    the Nginx config. Returns "Success" if successful,
    else an appropriate error.
    """

    if "data" not in request.form:
        return "Error", 400

    try:
        result = update_nginx_config(site_id, json.loads(request.form["data"]))
    except BaseException:  # pylint: disable=broad-except
        return "Error", 500
    else:
        if result is None:
            return "Success"
        else:
            return result, 500


if __name__ == "__main__":
    app.run()
