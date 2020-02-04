# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, Optional

from docker.client import DockerClient
from docker.models.containers import Container

from .conversions import convert_cpu_limit, convert_memory_limit
from .shared import gen_director_shared_params


def get_container(client: DockerClient, **filters: Any) -> Optional[Container]:
    filtered_containers = client.containers.list(filters=filters)

    if not filtered_containers:
        return None
    elif len(filtered_containers) == 1:
        return filtered_containers[0]
    else:
        raise ValueError("Multiple containers matched")


def gen_director_container_params(
    client: DockerClient, site_id: int, site_data: Dict[str, Any]
) -> Dict[str, Any]:
    env = {}
    if site_data.get("database_url"):
        env["DATABASE_URL"] = site_data["database_url"]

    params = gen_director_shared_params(client, site_id, site_data)

    params.update(
        {
            "working_dir": "/site",
            "nano_cpus": convert_cpu_limit(0.1),
            "mem_limit": convert_memory_limit("100MB"),
            "privileged": False,
            "environment": ["{}={}".format(name, val) for name, val in env.items()],
            "extra_hosts": {},
        }
    )

    return params


def get_or_create_container(
    client: DockerClient, name: str, *, run_params: Dict[str, Any],
) -> Container:
    container = get_container(client, name=name)

    if container is None:
        container = client.containers.run(name=name, detach=True, **run_params)

    return container
