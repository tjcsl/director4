# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict

from docker.client import DockerClient
from docker.types import Mount

from ..files import get_site_directory_path


def gen_director_shared_params(  # pylint: disable=unused-argument
    client: DockerClient, site_id: int, site_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Given the information on a site, returns the parameters that are common to both
    the main Swarm service and any additional containers launched related to the site."""

    env = {}
    if site_data.get("database_url"):
        env["DATABASE_URL"] = site_data["database_url"]

    return {
        "image": "alpine",
        "mounts": [
            Mount(
                type="bind",
                source=get_site_directory_path(site_id),
                target="/site",
                read_only=False,
            ),
        ],
        "init": True,
        "user": "root",
        "tty": False,
    }
