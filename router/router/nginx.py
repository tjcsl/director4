# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import string
import subprocess
from typing import Any, Dict

import jinja2

from . import settings

TEMPLATE_DIRECTORY = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))

nginx_template = jinja_env.get_template("nginx.conf")


def get_config_path(site_id: int) -> str:
    return os.path.join(settings.NGINX_DIRECTOR_DIR, "site-{}.conf".format(site_id))


def update_config(site_id: int, data: Dict[str, Any]) -> None:
    assert set(data["name"]) < set(string.ascii_letters + string.digits + "-")

    for domain in data["custom_domains"]:
        assert set(domain) < set(string.ascii_letters + string.digits + "-.")

    if not data["custom_domains"]:
        remove_config(site_id)

    text = nginx_template.render(
        {
            "id": site_id,
            "name": data["name"],
            "custom_domains": data["custom_domains"],
            "settings": settings,
        },
    )

    with open(get_config_path(site_id), "w") as f_obj:
        f_obj.write(text)

    subprocess.run(
        settings.NGINX_RELOAD_COMMAND, check=True,
    )


def remove_config(site_id: int) -> None:
    config_path = get_config_path(site_id)
    if os.path.exists(config_path):
        os.remove(config_path)
