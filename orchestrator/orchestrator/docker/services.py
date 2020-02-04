# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, Optional

from docker.client import DockerClient
from docker.models.services import Service
from docker.types import EndpointSpec, Mount, Resources, RestartPolicy, ServiceMode, UpdateConfig

from ..files import get_site_directory_path
from .conversions import convert_cpu_limit, convert_memory_limit


def get_service_by_name(client: DockerClient, service_name: str) -> Optional[Service]:
    filtered_services = client.services.list(filters={"name": service_name})
    if not filtered_services:
        return None
    elif len(filtered_services) == 1:
        return filtered_services[0]
    else:
        raise ValueError("Duplicate services")


def get_director_service_name(site_id: int) -> str:
    return "site_{:04d}".format(site_id)


def gen_director_service_params(  # pylint: disable=unused-argument
    client: DockerClient, site_id: int, site_data: Dict[str, Any]
) -> Dict[str, Any]:
    env = {
        "PORT": "80",
        "HOST": "0.0.0.0",
    }
    if site_data.get("database_url"):
        env["DATABASE_URL"] = site_data["database_url"]

    return {
        "name": get_director_service_name(site_id),
        "image": "alpine",
        "read_only": True,
        "command": [
            "sh",
            "-c",
            # We do this in the shell so that it can adapt to the path changing without updating the
            # Docker service
            'for path in /site{,/private,/public}/run.sh; do if [ -x "$path" ]; then exec "$path"; '
            "fi; done",
        ],
        "workdir": "/site/public",
        "mounts": [
            Mount(
                type="bind",
                source=get_site_directory_path(site_id),
                target="/site",
                read_only=False,
            ),
        ],
        "init": True,
        "networks": ["director-sites"],
        "env": ["{}={}".format(name, val) for name, val in env.items()],
        "resources": Resources(
            # 0.1 CPUs, 100M or so of memory
            cpu_limit=convert_cpu_limit(0.1),
            mem_limit=convert_memory_limit("100MB"),
        ),
        "user": "root",
        "log_driver": "json-file",
        "log_driver_options": {
            # Keep minimal logs
            "max-size": "500k",
            "max-file": "1",
        },
        "hosts": {},
        "stop_grace_period": 3,
        "endpoint_spec": EndpointSpec(mode="vip", ports={}),
        "tty": False,
        "mode": ServiceMode(mode="replicated", replicas=1),
        "restart_policy": RestartPolicy(condition="any", delay=5, max_attempts=0, window=0),
        "update_config": UpdateConfig(
            parallelism=1,
            order="stop-first",
            failure_action="rollback",
            max_failure_ratio=0,
            # delay and monitor are in nanoseconds (1e9 seconds)
            delay=int(5 * (10 ** 9)),
            monitor=int(5 * (10 ** 9)),
        ),
    }


def update_director_service(
    client: DockerClient, site_id: int, site_data: Dict[str, Any]
) -> Service:
    service = get_service_by_name(client, get_director_service_name(site_id))

    if service is None:
        service = client.services.create(**gen_director_service_params(client, site_id, site_data))
    else:
        service.update(**gen_director_service_params(client, site_id, site_data))

    return service


def restart_director_service(client: DockerClient, site_id: int) -> None:
    service = get_service_by_name(client, get_director_service_name(site_id))
    if service is None:
        raise ValueError("Service does not exist")

    if not service.force_update():
        raise Exception("Error restarting service")
