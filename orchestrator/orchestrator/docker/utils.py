# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import docker


def create_client() -> docker.client.DockerClient:
    """ Creates DockerClient instance from the environment.

    Returns:
        The created DockerClient instance.
    """

    return docker.from_env(version="auto")


def get_swarm_node_id(client: docker.client.DockerClient) -> str:
    return client.info()["Swarm"]["NodeID"]
