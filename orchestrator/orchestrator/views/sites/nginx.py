# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import traceback
from typing import Tuple, Union

from flask import Blueprint, request

from ...configs.nginx import disable_nginx_config, update_nginx_config
from ...docker.services import reload_nginx_config
from ...docker.utils import create_client
from ...exceptions import OrchestratorActionError

nginx = Blueprint("nginx", __name__)


@nginx.route("/sites/<int:site_id>/update-nginx", methods=["POST"])
def update_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
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
        traceback.print_exc()
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"


@nginx.route("/sites/reload-nginx", methods=["POST"])
def reload_nginx_page() -> Union[str, Tuple[str, int]]:
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


@nginx.route("/sites/<int:site_id>/disable-nginx", methods=["POST"])
def disable_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Disables the Nginx config for a given site.

    Should be used if deployment fails.
    """

    try:
        disable_nginx_config(site_id)
    except OrchestratorActionError as ex:
        traceback.print_exc()
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"
