import docker


def create_client() -> docker.client.DockerClient:
    """ Creates DockerClient instance from the environment.

    Returns:
        The created DockerClient instance.
    """

    return docker.from_env()


def delete_all_containers(client: docker.client.DockerClient, force: bool = False) -> None:
    if not force:
        print("Deleting all images.")

    for ctr in client.container.list():
        ctr.remove()


def main() -> None:
    client = create_client()
    docker_images = client.images.list()
    print("Images", docker_images)

    """
    ctr = client.containers.run("ubuntu:18.04", name="director_33797_test", detach=True)
    print(ctr)
    print(ctr.logs())
    containers_list = client.containers.list()
    for container in containers_list:
        print(container.image)
    """
    all_ctrs = client.containers.list(all=True)
    print("All Containers", all_ctrs)
    running_ctrs = client.containers.list(all=True)
    print("Running Containers", running_ctrs)


if __name__ == "__main__":
    main()
