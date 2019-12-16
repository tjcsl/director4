# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
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
        or re.search(r"^https?://[-a-zA-Z0-9.]+(/[-_a-zA-Z0-9.~])+$", new_data["primary_url_base"])
        is None
    ):
        return "Invalid primary URL"
    if not isinstance(new_data["no_redirect_domains"], list):
        return "Invalid 'no redirect' domains"
    for domain in new_data["no_redirect_domains"]:
        if (
            not isinstance(domain, str)
            or re.search(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*(\.[a-z][a-z0-9]*(-[a-z0-9]+)*)+$", domain)
            is None
        ):
            return "Invalid 'no redirect' domain {!r}".format(domain)
    if not isinstance(new_data["port"], int) or new_data["port"] < 10000:
        return "Invalid port"

    variables = {
        "DEBUG": settings.DEBUG,
        **new_data,
    }

    text = nginx_template.render(variables)

    try:
        with open("/etc/nginx/director.d/site-{}.conf".format(site_id), "w") as f_obj:
            f_obj.write(text)
    except OSError as ex:
        return "Error writing Nginx config: {}".format(ex)
    else:
        return None
