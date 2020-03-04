# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
import shutil
from typing import Any, Dict

import jinja2

from .. import settings
from ..exceptions import OrchestratorActionError
from ..files import get_site_directory_path

TEMPLATE_DIRECTORY = os.path.join(os.path.dirname(__file__), "templates")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
static_nginx_template = jinja_env.get_template("nginx-static.conf")


def update_static_nginx_config(site_id: int, data: Dict[str, Any]) -> None:
    """Returns None on success or a message on failure."""
    new_data = {}
    for key in ["name"]:
        if key not in data:
            raise OrchestratorActionError("Missing key {!r}".format(key))

        new_data[key] = data[key]

    # Some basic validation
    if (
        not isinstance(new_data["name"], str)
        or re.search(r"^[a-z0-9]+(-[a-z0-9]+)*$", new_data["name"]) is None
    ):
        raise OrchestratorActionError("Invalid name")

    variables = {
        "settings": settings,
        "id": site_id,
        "site_dir": get_site_directory_path(site_id),
        **new_data,
    }

    text = static_nginx_template.render(variables)

    nginx_config_path = os.path.join(
        settings.STATIC_NGINX_CONFIG_DIRECTORY, "site-{}.conf".format(site_id)
    )

    if os.path.exists(nginx_config_path):
        try:
            shutil.move(nginx_config_path, nginx_config_path + ".bak")
        except OSError as ex:
            raise OrchestratorActionError(
                "Error backing up old static Nginx config: {}".format(ex)
            ) from ex

    try:
        with open(nginx_config_path, "w") as f_obj:
            f_obj.write(text)
    except OSError as ex:
        raise OrchestratorActionError("Error writing static Nginx config: {}".format(ex)) from ex


def disable_static_nginx_config(site_id: int) -> None:
    """Returns None on success or a message on failure."""
    static_nginx_config_path = os.path.join(
        settings.STATIC_NGINX_CONFIG_DIRECTORY, "site-{}.conf".format(site_id)
    )

    if os.path.exists(static_nginx_config_path):
        try:
            shutil.move(static_nginx_config_path, static_nginx_config_path + ".bad")
        except OSError as ex:
            raise OrchestratorActionError(
                "Error moving old static Nginx config out of the way: {}".format(ex)
            ) from ex


def remove_static_nginx_config(site_id: int) -> None:
    """Returns None on success or a message on failure."""
    nginx_config_path = os.path.join(
        settings.STATIC_NGINX_CONFIG_DIRECTORY, "site-{}.conf".format(site_id)
    )

    if os.path.exists(nginx_config_path):
        try:
            os.remove(nginx_config_path)
        except OSError as ex:
            raise OrchestratorActionError(
                "Error moving old static Nginx config out of the way: {}".format(ex)
            ) from ex
