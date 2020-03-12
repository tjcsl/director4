# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, Tuple

import requests

from .. import settings
from ..exceptions import OrchestratorActionError


def make_registry_request(
    path: str, method: str = "GET", data: Dict[str, Any] = None, headers: Dict[str, Any] = None
) -> Tuple[int, Dict[str, Any], Dict[str, Any]]:
    """Makes a wide variety of requests against the Docker Registry API

    API described @ https://github.com/docker/distribution/blob/master/docs/spec/api.md
    """

    scheme = "https://"
    url = scheme + settings.DOCKER_REGISTRY_URL + "/v2" + path

    ssl_path = "/etc/docker/certs.d/{}/ca.crt".format(settings.DOCKER_REGISTRY_URL)
    extra_kwargs = {
        "data": data,
        "headers": headers,
        "timeout": settings.DOCKER_REGISTRY_TIMEOUT,
        "verify": ssl_path,
    }
    try:
        if method == "GET":
            response = requests.get(url, **extra_kwargs)
        elif method == "POST":
            response = requests.post(url, **extra_kwargs)
        elif method == "DELETE":
            response = requests.delete(url, **extra_kwargs)
        else:
            raise OrchestratorActionError("Invalid method.")
    except requests.exceptions.Timeout:
        raise OrchestratorActionError("Timeout on request to {}".format(path))

    status_code = response.status_code

    # This is request's special headers
    headers = response.headers
    try:
        content = response.json()
    except ValueError:
        content = response.content
    return status_code, content, headers


def remove_registry_image(image_name: str) -> None:
    _ = delete_registry_manifest(image_name)


"""
Docker Registry API

How images are structured
* Manifest
* Layer files
"""

"""
File System Hierarchy for an image:
Located at: /var/lib/registry/$name/_manifests/revisions/sha256/$hash

_manifests:
    - /_manifests
"""


def delete_registry_manifest(image_name: str) -> bool:
    # You MUST pass this header; See note in
    # https://docs.docker.com/registry/spec/api/#deleting-an-image
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    path = "/{}/manifests/latest".format(image_name)

    status_code, content, headers = make_registry_request(path, method="GET", headers=headers)
    if status_code != 200:
        # This captures when the image's reference
        # is no longer in the registry
        try:
            is_manifest_unknown_error = (
                status_code == 404 and content["errors"][0]["code"] == "MANIFEST_UNKNOWN"
            )
        except KeyError:
            is_manifest_unknown_error = False

        if is_manifest_unknown_error:
            raise OrchestratorActionError("Manifest unknown")
        raise OrchestratorActionError(
            "Status code {} while trying to connect to registry.".format(status_code)
        )

    # You CANNOT use the digests reported in the response content
    # You MUST use the "docker-content-digest" header in the
    # manifest retrieval response
    content_digest_header = "docker-content-digest"
    # This should never happen, but just in case
    if content_digest_header not in headers:
        raise OrchestratorActionError("{} not found in response.".format(content_digest_header))

    digest = headers[content_digest_header]

    # The registry is weird in that you need
    # to pass the digest in as the reference
    # during image delete operations
    status_code, content, headers = make_registry_request(
        "/{}/manifests/{}".format(image_name, digest), method="DELETE"
    )
    # 202 - accepted here is success
    if status_code != 202:
        raise OrchestratorActionError(
            "Status code {} while trying to connect to registry.".format(status_code)
        )
    return True


def get_registry_catalog() -> Dict[str, Any]:
    status_code, content, _ = make_registry_request("/_catalog", method="GET")
    if status_code != 200:
        raise OrchestratorActionError(
            "Status code {} while trying to connect to registry.".format(status_code)
        )

    if isinstance(content, dict):
        return content
    else:
        return None
