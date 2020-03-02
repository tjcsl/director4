# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
from typing import Any, Dict, cast

import jinja2
from docker.client import DockerClient
from docker.errors import ImageNotFound

from .. import settings
from ..exceptions import OrchestratorActionError

TEMPLATE_DIRECTORY = os.path.join(os.path.dirname(__file__), "templates")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
dockerfile_template = jinja_env.get_template("Dockerfile")


def get_docker_image_directory(image_name: str) -> str:
    return os.path.join(settings.DOCKERFILE_DIRECTORY, image_name)


def build_custom_docker_image(client: DockerClient, image_data: Dict[str, Any]) -> None:
    image_name = image_data["name"]
    parent_name = image_data["parent_name"]
    full_install_command = image_data["full_install_command"]

    context = {
        "parent": parent_name,
        "maintainer": "CSL",
        "full_install_command": full_install_command,
    }
    dockerfile_content = dockerfile_template.render(context)

    image_directory = get_docker_image_directory(image_name)

    # This path used to be the Dockerfile, so to handle the transition
    # we need to remove it if it exists.
    if os.path.isfile(image_directory):
        os.remove(image_directory)

    if not os.path.exists(image_directory):
        os.mkdir(image_directory, mode=0o755)

    dockerfile_path = os.path.join(image_directory, "Dockerfile")

    try:
        with open(dockerfile_path, "w+") as f_obj:
            f_obj.write(dockerfile_content)
    except OSError as ex:
        raise OrchestratorActionError("Error writing Dockerfile: {}".format(ex))

    # We want to delete intermediate containers during the build process
    image, build_logs = client.images.build(
        path=image_directory, rm=True, dockerfile="Dockerfile", tag=image_name
    )


def remove_docker_image(client: DockerClient, name: str) -> None:
    try:
        client.images.remove(name)
    except ImageNotFound:
        # This is the desired state; don't throw an error
        pass


def push_custom_docker_image(client: DockerClient, image_name: str) -> str:
    try:
        img = client.images.get(image_name)
    except ImageNotFound:
        raise OrchestratorActionError("Image not found with name: {}".format(image_name))

    # We need to tag before we push
    remote_repository = settings.DOCKER_REGISTRY_URL + "/" + image_name

    if not img.tag(remote_repository):
        raise OrchestratorActionError("Error")

    # Long-running
    return cast(
        str, client.images.push(remote_repository, auth_config=settings.DOCKER_REGISTRY_AUTH_CONFIG)
    )
