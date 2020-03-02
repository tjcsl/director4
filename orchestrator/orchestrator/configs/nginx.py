# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
import shutil
from typing import Any, Dict

import jinja2

from .. import settings
from ..exceptions import OrchestratorActionError

TEMPLATE_DIRECTORY = os.path.join(os.path.dirname(__file__), "templates")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
nginx_template = jinja_env.get_template("nginx.conf")


def update_nginx_config(site_id: int, data: Dict[str, Any]) -> None:
    """Returns None on success or a message on failure."""
    new_data = {}
    for key in ["name", "no_redirect_domains", "primary_url_base", "type"]:
        if key not in data:
            raise OrchestratorActionError("Missing key {!r}".format(key))

        new_data[key] = data[key]

    # Some basic validation
    if (
        not isinstance(new_data["name"], str)
        or re.search(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", new_data["name"]) is None
    ):
        raise OrchestratorActionError("Invalid name")
    if new_data["primary_url_base"] is not None and (
        not isinstance(new_data["primary_url_base"], str)
        or re.search(
            r"https?://[-a-zA-Z0-9.]+(:\d+)?(/([-_a-zA-Z0-9.~]+/)*[-_a-zA-Z0-9.~]*)?$",
            new_data["primary_url_base"],
        )
        is None
    ):
        raise OrchestratorActionError("Invalid primary URL")
    if not isinstance(new_data["no_redirect_domains"], list):
        raise OrchestratorActionError("Invalid 'no redirect' domains")
    for domain in new_data["no_redirect_domains"]:
        if not isinstance(domain, str) or (
            re.search(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*(\.[a-z][a-z0-9]*(-[a-z0-9]+)*)+$", domain)
            is None
            and re.search(r"^((\d+\.){3}\d+|([0-9a-fA-F]|:):[0-9a-fA-F:]*)$", domain) is None
        ):
            raise OrchestratorActionError("Invalid 'no redirect' domain {!r}".format(domain))

    variables = {
        "settings": settings,
        "id": site_id,
        **new_data,
    }

    text = nginx_template.render(variables)

    nginx_config_path = os.path.join(
        settings.NGINX_CONFIG_DIRECTORY, "site-{}.conf".format(site_id)
    )

    if os.path.exists(nginx_config_path):
        try:
            shutil.move(nginx_config_path, nginx_config_path + ".bak")
        except OSError as ex:
            raise OrchestratorActionError(
                "Error backing up old Nginx config: {}".format(ex)
            ) from ex

    try:
        with open(nginx_config_path, "w") as f_obj:
            f_obj.write(text)
    except OSError as ex:
        raise OrchestratorActionError("Error writing Nginx config: {}".format(ex)) from ex


def disable_nginx_config(site_id: int) -> None:
    """Returns None on success or a message on failure."""
    nginx_config_path = os.path.join(
        settings.NGINX_CONFIG_DIRECTORY, "site-{}.conf".format(site_id)
    )

    if os.path.exists(nginx_config_path):
        try:
            shutil.move(nginx_config_path, nginx_config_path + ".bad")
        except OSError as ex:
            raise OrchestratorActionError(
                "Error moving old Nginx config out of the way: {}".format(ex)
            ) from ex


def remove_nginx_config(site_id: int) -> None:
    """Returns None on success or a message on failure."""
    nginx_config_path = os.path.join(
        settings.NGINX_CONFIG_DIRECTORY, "site-{}.conf".format(site_id)
    )

    if os.path.exists(nginx_config_path):
        try:
            os.remove(nginx_config_path)
        except OSError as ex:
            raise OrchestratorActionError(
                "Error moving old Nginx config out of the way: {}".format(ex)
            ) from ex
