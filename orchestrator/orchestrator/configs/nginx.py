# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
import subprocess
from typing import Any, Dict, Optional

import jinja2

from .. import settings

TEMPLATE_DIRECTORY = os.path.join(os.path.dirname(__file__), "templates")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
nginx_template = jinja_env.get_template("nginx.conf")


def update_nginx_config(site_id: int, data: Dict[str, Any]) -> Optional[str]:
    """Returns None on success or a message on failure."""
    new_data = {
        key: data[key] for key in ["name", "port", "no_redirect_domains", "primary_url_base"]
    }

    # Some basic validation
    if (
        not isinstance(new_data["name"], str)
        or re.search(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", new_data["name"]) is None
    ):
        return "Invalid name"
    if new_data["primary_url_base"] is not None and (
        not isinstance(new_data["primary_url_base"], str)
        or re.search(
            r"https?://[-a-zA-Z0-9.]+(:\d+)?(/([-_a-zA-Z0-9.~]+/)*[-_a-zA-Z0-9.~]*)?$",
            new_data["primary_url_base"],
        )
        is None
    ):
        return "Invalid primary URL"
    if not isinstance(new_data["no_redirect_domains"], list):
        return "Invalid 'no redirect' domains"
    for domain in new_data["no_redirect_domains"]:
        if not isinstance(domain, str) or (
            re.search(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*(\.[a-z][a-z0-9]*(-[a-z0-9]+)*)+$", domain)
            is None
            and re.search(r"^((\d+\.){3}\d+|([0-9a-fA-F]|:):[0-9a-fA-F:]*)$", domain) is None
        ):
            return "Invalid 'no redirect' domain {!r}".format(domain)
    if not isinstance(new_data["port"], int) or new_data["port"] < 10000:
        return "Invalid port"

    variables = {
        "settings": settings,
        **new_data,
    }

    text = nginx_template.render(variables)

    nginx_config_path = "/etc/nginx/director.d/site-{}.conf".format(site_id)

    try:
        with open(nginx_config_path, "w") as f_obj:
            f_obj.write(text)
    except OSError as ex:
        return "Error writing Nginx config: {}".format(ex)

    try:
        subprocess.run(
            settings.NGINX_CONFIG_CHECK_COMMAND,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        try:
            os.rename(nginx_config_path, nginx_config_path + ".bak")
        except OSError:
            return (
                "Error checking Nginx config for errors (also unable to move site config out of "
                "the way)"
            )
        else:
            return (
                "Error checking Nginx config for errors (site config has been renamed with a .bak "
                "extension)"
            )

    try:
        subprocess.run(
            settings.NGINX_CONFIG_RELOAD_COMMAND,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "Error reloading Nginx config"

    return None
