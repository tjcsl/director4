# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import traceback

from flask import Flask, request

from .configs.nginx import disable_nginx_config, update_nginx_config
from .docker.services import reload_nginx_config, restart_director_service, update_director_service
from .docker.utils import create_client
from .exceptions import OrchestratorActionError
from .files import SiteFilesException, ensure_site_directories_exist, get_site_file

app = Flask(__name__)


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
    except OrchestratorActionError as ex:
        traceback.print_exc()
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/<int:site_id>/restart-docker-service", methods=["POST"])
def restart_docker_service_page(site_id: int):
    """Restarts the Docker service for a given site."""

    try:
        restart_director_service(create_client(), site_id)
    except OrchestratorActionError as ex:
        traceback.print_exc()
        return str(ex), 500
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
        update_nginx_config(site_id, json.loads(request.form["data"]))
    except OrchestratorActionError as ex:
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/reload-nginx", methods=["POST"])
def reload_nginx_page():
    """Reload the Nginx service's configuration."""
    try:
        reload_nginx_config(create_client())
    except OrchestratorActionError as ex:
        traceback.print_exc()
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/<int:site_id>/disable-nginx", methods=["POST"])
def disable_nginx_page(site_id: int):
    """Disables the Nginx config for a given site.

    Should be used if deployment fails.
    """

    try:
        disable_nginx_config(site_id)
    except OrchestratorActionError as ex:
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/<int:site_id>/files/get", methods=["GET"])
def get_file_page(site_id: int):
    """Get a file from a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        return get_site_file(site_id, request.args["path"])
    except SiteFilesException as ex:
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"


if __name__ == "__main__":
    app.run()
