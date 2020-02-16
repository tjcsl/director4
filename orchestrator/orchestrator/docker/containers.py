# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, Optional

from docker.client import DockerClient
from docker.models.containers import Container
from docker.types import LogConfig

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
    extra_env: Dict[str, str] = {}

    params = gen_director_shared_params(client, site_id, site_data)

    env = params.pop("env", [])
    env.extend("{}={}".format(name, val) for name, val in extra_env.items())

    params.update(
        {
            "working_dir": "/site",
            "nano_cpus": convert_cpu_limit(site_data["resource_limits"]["cpus"]),
            "mem_limit": convert_memory_limit(site_data["resource_limits"]["mem_limit"]),
            "privileged": False,
            "read_only": False,
            "environment": env,
            "log_config": LogConfig(
                type=LogConfig.types.JSON, config={"max-size": "1k", "max-file": "1"},
            ),
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
