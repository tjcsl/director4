from typing import Optional

from docker.client import DockerClient
from docker.models.services import Service
from docker.types import EndpointSpec, Resources, RestartPolicy

from .conversions import convert_cpu_limit, convert_memory_limit


def is_service_existing(client: DockerClient, service_name: str) -> bool:
    filtered_services = client.services.list(filters={"name": service_name})
    print("Filtered Services:", filtered_services)
    return len(filtered_services) > 0


def create_service(client: DockerClient, service_name: str) -> Optional[Service]:
    restart_policy = RestartPolicy(condition="on-failure")

    # cpu_limit: Limit to 0.1 of a CPU
    cpu_limit = convert_cpu_limit(0.1)

    # memory_limit = convert_memory_limit("50M")
    # memory_limit: 50M
    memory_limit = convert_memory_limit(str(float(5e7)))

    resource = Resources(cpu_limit=cpu_limit, mem_limit=memory_limit)

    # Mapping ports
    endpoint_spec = EndpointSpec(mode="vip", ports={8080: 80})

    image_name = "site_test_1"
    service = client.services.create(
        image=image_name,
        name=service_name,
        restart_policy=restart_policy,
        resources=resource,
        endpoint_spec=endpoint_spec,
    )

    return service
