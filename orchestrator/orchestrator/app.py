# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

# import logging
import json

from flask import Flask, request  # , jsonify, redirect, url_for

from .configs.nginx import update_nginx_config
from .containers.containers import demo_main

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


@app.route("/sites/<int:site_id>/create-docker-container")
def create_docker_container_page(site_id: int):  # pylint: disable=unused-argument
    """Creates a Docker image/container for a given site.

    Based on the provided site_id and data, creates the
    image/container. Returns "Success" if successful,
    else an appropriate error.
    """

    if "data" not in request.args:
        return "Error", 400

    try:
        result = None
    except BaseException:  # pylint: disable=broad-except
        return "Error", 500
    else:
        if result is None:
            return "Success"
        else:
            return result, 500


@app.route("/sites/<int:site_id>/update-nginx")
def update_nginx_page(site_id: int):
    """Updates the Nginx config for a given site.

    Based on the provided site_id and data, updates
    the Nginx config. Returns "Success" if successful,
    else an appropriate error.
    """

    if "data" not in request.args:
        return "Error", 400

    try:
        result = update_nginx_config(site_id, json.loads(request.args["data"]))
    except BaseException:  # pylint: disable=broad-except
        return "Error", 500
    else:
        if result is None:
            return "Success"
        else:
            return result, 500


@app.route("/demo", methods=["GET", "POST"])
def demo_page():
    """Runs demonstration of Director 4.0
    capabilities.

    Returns the demonstration response.
    """
    return str(demo_main())


if __name__ == "__main__":
    app.run()
