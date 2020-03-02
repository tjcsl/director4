# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import traceback
from typing import Tuple, Union

from flask import Blueprint, current_app, request

from ..configs.nginx_static import (
    disable_static_nginx_config,
    remove_static_nginx_config,
    update_static_nginx_config,
)
from ..docker.services import reload_static_nginx_config
from ..docker.utils import create_client
from ..exceptions import OrchestratorActionError
from ..files import ensure_site_directories_exist

nginx_static = Blueprint("nginx_static", __name__)


@nginx_static.route("/sites/<int:site_id>/update-static-nginx", methods=["POST"])
def update_static_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Updates the static Nginx config for a given site.

    Based on the provided site_id and data, updates
    the Nginx config. Returns "Success" if successful,
    else an appropriate error.
    """

    if "data" not in request.form:
        return "Error", 400

    try:
        ensure_site_directories_exist(site_id)

        update_static_nginx_config(site_id, json.loads(request.form["data"]))
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@nginx_static.route("/sites/reload-static-nginx", methods=["POST"])
def reload_nginx_page() -> Union[str, Tuple[str, int]]:
    """Reload the static Nginx service's configuration."""
    try:
        reload_static_nginx_config(create_client())
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@nginx_static.route("/sites/<int:site_id>/disable-static-nginx", methods=["POST"])
def disable_static_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Disables the static Nginx config for a given site.

    Should be used if deployment fails.
    """

    try:
        disable_static_nginx_config(site_id)
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@nginx_static.route("/sites/<int:site_id>/remove-static-nginx", methods=["POST"])
def remove_static_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Disables the static Nginx config for a given site.

    Should be used if deployment fails.
    """

    try:
        remove_static_nginx_config(site_id)
    except OrchestratorActionError as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"
