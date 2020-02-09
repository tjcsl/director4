# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import traceback
from typing import Tuple, Union

from flask import Flask, request

from .docker.services import (
    remove_director_service,
    restart_director_service,
    update_director_service,
)
from .docker.utils import create_client
from .exceptions import OrchestratorActionError
from .files import ensure_site_directories_exist
from .views.sites.files import files as files_blueprint
from .views.sites.nginx import nginx as nginx_blueprint

app = Flask(__name__)
app.register_blueprint(files_blueprint)
app.register_blueprint(nginx_blueprint)


@app.route("/ping")
def ping_page() -> str:
    """Checks whether the orchestrator is functional.

    Returns a provided message or else "Pong".
    """

    return "{}\n".format(request.args.get("message", "Pong"))


@app.route("/sites/<int:site_id>/update-docker-service", methods=["POST"])
def update_docker_service_page(site_id: int) -> Union[str, Tuple[str, int]]:
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
def restart_docker_service_page(site_id: int) -> Union[str, Tuple[str, int]]:
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


@app.route("/sites/<int:site_id>/remove-docker-service", methods=["POST"])
def remove_docker_service_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Removes the Docker service for a given site."""

    try:
        remove_director_service(create_client(), site_id)
    except OrchestratorActionError as ex:
        traceback.print_exc()
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"


if __name__ == "__main__":
    app.run()
