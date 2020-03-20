# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import traceback
from typing import Tuple, Union

from flask import Blueprint, current_app, request

from ..docker.images import remove_docker_image
from ..docker.registry import remove_registry_image
from ..docker.services import (
    remove_director_service,
    restart_director_service,
    update_director_service,
)
from ..docker.utils import create_client
from ..exceptions import OrchestratorActionError

docker_blueprint = Blueprint("docker", __name__)


@docker_blueprint.route("/sites/<int:site_id>/update-docker-service", methods=["POST"])
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
        update_director_service(create_client(), site_id, json.loads(request.form["data"]))
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@docker_blueprint.route("/sites/<int:site_id>/restart-docker-service", methods=["POST"])
def restart_docker_service_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Restarts the Docker service for a given site."""

    try:
        restart_director_service(create_client(), site_id)
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@docker_blueprint.route("/sites/<int:site_id>/remove-docker-service", methods=["POST"])
def remove_docker_service_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Removes the Docker service for a given site."""

    try:
        remove_director_service(create_client(), site_id)
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@docker_blueprint.route("/sites/remove-docker-image", methods=["POST"])
def remove_docker_image_page() -> Union[str, Tuple[str, int]]:
    """Removes the Docker image with the given name."""

    if "name" not in request.args:
        return "Error", 400

    try:
        remove_docker_image(create_client(), request.args["name"])
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@docker_blueprint.route("/sites/remove-registry-image", methods=["POST"])
def remove_registry_image_page() -> Union[str, Tuple[str, int]]:
    """Removes the given Docker image with the given name
    from the Docker registry."""

    if "name" not in request.args:
        return "Error", 400

    try:
        remove_registry_image(request.args["name"])
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"
