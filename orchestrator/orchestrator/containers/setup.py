# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import docker


def create_client() -> docker.client.DockerClient:
    """ Creates DockerClient instance from the environment.

    Returns:
        The created DockerClient instance.
    """

    return docker.from_env()


def is_container_running(client: docker.client.DockerClient, ctr_name_or_id):
    running_by_id = client.containers.list(filters={"id": ctr_name_or_id})
    running_by_name = client.containers.list(filters={"name": ctr_name_or_id})
    return len(running_by_id) > 0 or len(running_by_name) > 0


def delete_all_containers(client: docker.client.DockerClient, force: bool = False) -> None:
    """ Deletes all containers.

    Useful when resetting the environment. This is dangerous.

    Args:
        force: Whether to not prompt for confirmation on deletion.
    """
    if not force:
        print("Starting to delete all images.")

    for ctr in client.containers.list():
        running = is_container_running(client, ctr.name)
        if running:
            print("Removing container {}".format(ctr.name))
        ctr.remove()


def main() -> None:
    client = create_client()
    docker_images = client.images.list()
    print("Images", docker_images)

    all_ctrs = client.containers.list(all=True)
    print("All Containers", all_ctrs)
    running_ctrs = client.containers.list()
    print("Running Containers", running_ctrs)

    delete_all_containers(client)

    ctr = client.containers.run(
        "ubuntu:18.04", detach=True, tty=True, stdin_open=True, name="director_theo_test"
    )
    rc, output = ctr.exec_run("whoami")
    print(rc)
    print(output)


if __name__ == "__main__":
    main()
