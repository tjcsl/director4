# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, List, Optional, cast

import docker
from docker.client import DockerClient
from docker.models.services import Service
from docker.types import EndpointSpec, Resources, RestartPolicy, ServiceMode, UpdateConfig

from .. import settings
from ..exceptions import OrchestratorActionError
from .conversions import convert_cpu_limit, convert_memory_limit
from .shared import gen_director_shared_params
from .utils import get_swarm_node_id


def get_service_by_name(client: DockerClient, service_name: str) -> Optional[Service]:
    # The "filters" appear to do an "a in b" check, not an "a == b" check.
    # We need to confirm that they match
    filtered_services = [
        service
        for service in client.services.list(filters={"name": service_name})
        if service.name == service_name
    ]
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
    extra_env = {
        "PORT": "80",
        "HOST": "0.0.0.0",
    }

    params = gen_director_shared_params(client, site_id, site_data)

    env = params.pop("env", [])
    env.extend("{}={}".format(name, val) for name, val in extra_env.items())

    # We do the run.sh path detection in the shell so that it can adapt to the path changing without
    # updating the Docker service
    # The killing of the child process is based off of
    # https://unix.stackexchange.com/a/146770/306760
    shell_command = """date +'DIRECTOR: Starting server at %Y-%m-%d %H:%M:%S %Z'
# See docs/UMASK.md before touching this
umask "$1"
for path in /site/run.sh /site/private/run.sh /site/public/run.sh; do
    if [ -x "$path" ]; then
        term() {
            date +'DIRECTOR: Stopping server at %Y-%m-%d %H:%M:%S %Z'
            kill "$child"
        }
        trap term TERM

        "$path" &
        child="$!"

        while ! wait; do true; done
        exec date +'DIRECTOR: Stopped server at %Y-%m-%d %H:%M:%S %Z'
    fi
done
echo 'DIRECTOR: No run.sh file found -- if it exists, make sure it is set as executable'
exec sleep 2147483647"""

    params.update(
        {
            "name": get_director_service_name(site_id),
            "read_only": True,
            # See docs/UMASK.md before touching this
            "command": ["sh", "-c", shell_command, "sh", oct(settings.SITE_UMASK)[2:]],
            "workdir": "/site/public",
            "networks": ["director-sites"],
            "resources": Resources(
                # 0.1 CPUs, 100M or so of memory
                cpu_limit=convert_cpu_limit(site_data["resource_limits"]["cpus"]),
                mem_limit=convert_memory_limit(site_data["resource_limits"]["mem_limit"]),
            ),
            "env": env,
            "log_driver": "json-file",
            "log_driver_options": {
                # Keep minimal logs
                "max-size": "500k",
                "max-file": "1",
            },
            "hosts": params.pop("extra_hosts"),
            "stop_grace_period": 3,
            "endpoint_spec": EndpointSpec(mode="vip", ports={}),
            "mode": ServiceMode(
                mode="replicated", replicas=1 if site_data["is_being_served"] else 0
            ),
            "restart_policy": RestartPolicy(condition="any", delay=5, max_attempts=5, window=0),
            "update_config": UpdateConfig(
                parallelism=1,
                order="stop-first",
                failure_action="rollback",
                max_failure_ratio=0,
                # delay and monitor are in nanoseconds (1e9 seconds)
                delay=int(5 * (10**9)),
                monitor=int(5 * (10**9)),
            ),
        }
    )

    return params


def update_director_service(
    client: DockerClient, site_id: int, site_data: Dict[str, Any]
) -> Optional[Service]:
    service = get_service_by_name(client, get_director_service_name(site_id))

    if service is None:
        service = client.services.create(**gen_director_service_params(client, site_id, site_data))
    else:
        service.update(**gen_director_service_params(client, site_id, site_data))

    return service


def restart_director_service(client: DockerClient, site_id: int) -> None:
    service = get_service_by_name(client, get_director_service_name(site_id))
    if service is None:
        raise OrchestratorActionError("Service does not exist")

    try:
        if not service.force_update():
            raise OrchestratorActionError("Error restarting service")
    except docker.errors.APIError as ex:
        if "update out of sequence" in str(ex):
            pass
        else:
            raise


def remove_director_service(client: DockerClient, site_id: int) -> None:
    service = get_service_by_name(client, get_director_service_name(site_id))

    if service is None:
        # The service doesn't exist. This is what we want; don't throw an
        # error.
        return

    service.remove()


def list_service_tasks_for_node(service: Service, node_id: str) -> List[Dict[str, Any]]:
    return cast(List[Dict[str, Any]], service.tasks(filters={"node": node_id}))


def reload_nginx_config(client: DockerClient) -> None:
    service = get_service_by_name(client, settings.NGINX_SERVICE_NAME)

    node_id = get_swarm_node_id(client)
    tasks = list_service_tasks_for_node(service, node_id=node_id)

    for task in tasks:
        if task["DesiredState"] == "running" and task["Status"]["State"] == "running":
            container_id = task["Status"]["ContainerStatus"]["ContainerID"]

            container = client.containers.get(container_id)

            exit_code, _ = container.exec_run(
                ["nginx", "-s", "reload"],
                stdout=False,
                stderr=True,
                stdin=False,
                tty=False,
                privileged=False,
                user="root",
                detach=False,
                stream=False,
                socket=False,
                workdir="/",
                demux=False,
            )

            if exit_code != 0:
                raise OrchestratorActionError("Error reloading Nginx config")
