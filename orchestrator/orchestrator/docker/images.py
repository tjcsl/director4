# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
from typing import Any, Dict

import jinja2
from docker.client import DockerClient

from .. import settings
from ..exceptions import OrchestratorActionError

TEMPLATE_DIRECTORY = os.path.join(os.path.dirname(__file__), "templates")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))
dockerfile_template = jinja_env.get_template("Dockerfile")


def get_dockerfile_path(base_path: str) -> str:
    return os.path.join(settings.DOCKERFILE_DIRECTORY, base_path)


def build_custom_docker_image(client: DockerClient, image_data: Dict[str, Any]) -> None:
    image_name = image_data["name"]
    parent_name = image_data["parent_name"]
    full_install_command = image_data["full_install_command"]

    file_path = get_dockerfile_path(image_name)

    context = {
        "parent": parent_name,
        "maintainer": "CSL",
        "full_install_command": full_install_command,
    }
    content = dockerfile_template.render(context)

    try:
        with open(file_path, "w+") as f_obj:
            f_obj.write(content)
    except OSError as ex:
        raise OrchestratorActionError("Error writing Dockerfile: {}".format(ex))

    # We want to delete intermediate containers during the build process
    image, build_logs = client.images.build(
        path=settings.DOCKERFILE_DIRECTORY, rm=True, dockerfile=image_name, tag=image_name
    )
