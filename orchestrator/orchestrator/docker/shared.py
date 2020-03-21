# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
from typing import Any, Dict

from docker.client import DockerClient
from docker.types import Mount

from .. import settings
from ..files import get_site_directory_path


def gen_director_shared_params(  # pylint: disable=unused-argument
    client: DockerClient, site_id: int, site_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Given the information on a site, returns the parameters that are common to both
    the main Swarm service and any additional containers launched related to the site."""

    env = {"TZ": settings.TIMEZONE}
    if site_data.get("database_url"):
        env["DATABASE_URL"] = site_data["database_url"]

    if site_data["docker_image"]["is_custom"]:
        image_name = settings.DOCKER_REGISTRY_URL + "/" + site_data["docker_image"]["name"]
    else:
        image_name = site_data["docker_image"]["name"]

    return {
        "image": image_name,
        "mounts": [
            Mount(
                type="bind",
                source=get_site_directory_path(site_id),
                target="/site",
                read_only=False,
            ),
            Mount(
                type="bind",
                source=os.path.join(get_site_directory_path(site_id), ".home"),
                target="/root",
                read_only=False,
            ),
            Mount(
                type="tmpfs",
                source=None,
                target="/tmp",
                read_only=False,
                tmpfs_size="10m",
                tmpfs_mode=0o1777,
            ),
            Mount(
                type="tmpfs",
                source=None,
                target="/run",
                read_only=False,
                tmpfs_size="5m",
                tmpfs_mode=0o1777,
            ),
        ],
        "init": True,
        "user": "root",
        "tty": False,
        # These options are inconsistently named between sites and containers, so we
        # picked one name and rewrite it for the other.
        "env": ["{}={}".format(name, val) for name, val in env.items()],
        "extra_hosts": {},
    }
