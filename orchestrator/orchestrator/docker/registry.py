# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import requests

from .. import settings
from ..exceptions import OrchestratorActionError


def make_registry_request(
    path: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Union[Dict[str, Any], str], Mapping[str, Any]]:
    """Makes a wide variety of requests against the Docker Registry API

    API described @ https://github.com/docker/distribution/blob/master/docs/spec/api.md
    """

    scheme = "https://"
    url = scheme + settings.DOCKER_REGISTRY_URL + "/v2" + path

    ssl_cert_path = "/etc/docker/certs.d/{}/client.cert".format(settings.DOCKER_REGISTRY_URL)
    ssl_key_path = "/etc/docker/certs.d/{}/client.key".format(settings.DOCKER_REGISTRY_URL)
    ssl_ca_path = "/etc/docker/certs.d/{}/ca.crt".format(settings.DOCKER_REGISTRY_URL)

    cert_paths: Optional[Tuple[str, str]]
    if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
        cert_paths = (ssl_cert_path, ssl_key_path)
    else:
        cert_paths = None

    try:
        if method not in {"GET", "POST", "DELETE"}:
            raise OrchestratorActionError("Invalid method")

        response = requests.request(
            method,
            url,
            data=data,
            headers=headers,
            timeout=settings.DOCKER_REGISTRY_TIMEOUT,
            cert=cert_paths,
            verify=ssl_ca_path,
        )
    except requests.exceptions.Timeout as ex:
        raise OrchestratorActionError("Timeout on request to {}".format(path)) from ex

    status_code = response.status_code

    try:
        content = response.json()
    except ValueError:
        content = response.content

    return status_code, content, response.headers


def remove_registry_image(image_name: str) -> None:
    delete_registry_manifest(image_name)


# Docker Registry API
#
# How images are structured
# * Manifest
# * Layer files
#
# File System Hierarchy for an image:
# Located at: /var/lib/registry/$name/_manifests/revisions/sha256/$hash
#
# _manifests:
#     - /_manifests


def delete_registry_manifest(image_name: str) -> None:
    status_code, content, resp_headers = make_registry_request(
        "/{}/manifests/latest".format(image_name),
        method="GET",
        # You MUST pass this header; See note in
        # https://docs.docker.com/registry/spec/api/#deleting-an-image
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )

    if status_code != 200:
        # This captures when the image's reference
        # is no longer in the registry
        try:
            is_manifest_unknown_error = (
                status_code == 404
                and isinstance(content, dict)
                and content["errors"][0]["code"] == "MANIFEST_UNKNOWN"
            )
        except KeyError:
            is_manifest_unknown_error = False

        if is_manifest_unknown_error:
            # The manifest did not exist, in which case we have nothing to do
            return

        raise OrchestratorActionError(
            "Error {} while trying to connect to registry".format(status_code)
        )

    # You CANNOT use the digests reported in the response content
    # You MUST use the "docker-content-digest" header in the
    # manifest retrieval response
    content_digest_header = "docker-content-digest"
    # This should never happen, but just in case
    if content_digest_header not in resp_headers:
        raise OrchestratorActionError("{} not found in response".format(content_digest_header))

    digest = resp_headers[content_digest_header]

    # The registry is weird in that you need
    # to pass the digest in as the reference
    # during image delete operations
    status_code, content, resp_headers = make_registry_request(
        "/{}/manifests/{}".format(image_name, digest), method="DELETE"
    )

    # 202 is success
    # 404 Not Found means the manifest did not exist, in which case we have nothing to do
    if status_code not in (202, 404):
        raise OrchestratorActionError(
            "Error {} while trying to connect to registry".format(status_code)
        )


def get_registry_catalog() -> Optional[Dict[str, Any]]:
    status_code, content, _ = make_registry_request("/_catalog", method="GET")
    if status_code != 200:
        raise OrchestratorActionError(
            "Status code {} while trying to connect to registry.".format(status_code)
        )

    if isinstance(content, dict):
        return content
    else:
        return None
