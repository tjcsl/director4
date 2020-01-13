# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
from typing import Any, Dict, Iterator, Tuple, Union

from django.conf import settings
from django.db.models import Max

from ...utils.appserver import appserver_open_http_request, iter_pingable_appservers
from ...utils.balancer import balancer_open_http_request, iter_pingable_balancers
from .models import Site


def find_pingable_appservers(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging appservers"
    pingable_appservers = list(iter_pingable_appservers())
    yield "Pingable appservers: {}".format(pingable_appservers)

    scope["pingable_appservers"] = pingable_appservers


def select_site_port(site: Site, scope: Dict[str, Any]) -> Iterator[Union[Tuple[str, str], str]]:
    port = Site.objects.exclude(id=site.id).aggregate(Max("port"))["port__max"]
    if port is None:
        port = settings.DIRECTOR_MIN_PORT
    else:
        port += 1

    while True:
        yield "Checking if port {} is open".format(port)
        for i in scope["pingable_appservers"]:
            res = appserver_open_http_request(i, "/check-port/{}".format(port))
            if res.text != "":
                break
        else:
            break

        port += 1

    # We found an open port
    site.port = port
    site.save()


def update_appserver_nginx_config(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    for i in scope["pingable_appservers"]:
        yield "Updating appserver {} Nginx configs".format(i)
        appserver_open_http_request(
            i,
            "/sites/{}/update-nginx".format(site.id),
            params={"data": json.dumps(site.serialize_for_appserver())},
        )

    yield "Updated all appservers"


def create_docker_container(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = scope["pingable_appservers"][0]

    yield "Connecting to appserver {} to create Docker container".format(appserver)
    appserver_open_http_request(
        appserver,
        "/sites/{}/create-docker-container".format(site.id),
        params={"data": json.dumps(site.serialize_for_appserver())},
    )

    yield "Created Docker container"


def update_balancer_nginx_config(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging balancers"
    pingable_balancers = list(iter_pingable_balancers())
    yield "Pingable balancers: {}".format(pingable_balancers)

    for i in pingable_balancers:
        yield "Updating balancer {}".format(i)
        balancer_open_http_request(
            i,
            "/sites/{}/update-nginx".format(site.id),
            params={"data": json.dumps(site.serialize_for_balancer())},
        )
        yield "Updated balancer {}".format(i)
