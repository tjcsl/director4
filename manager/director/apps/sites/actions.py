# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import random
from typing import Any, Dict, Iterator, Tuple, Union

from ...utils.appserver import (
    AppserverProtocolError,
    appserver_open_http_request,
    iter_pingable_appservers,
)
from ...utils.balancer import balancer_open_http_request, iter_pingable_balancers
from .models import Site


def find_pingable_appservers(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging appservers"
    pingable_appservers = list(iter_pingable_appservers())
    yield "Pingable appservers: {}".format(pingable_appservers)

    scope["pingable_appservers"] = pingable_appservers


def update_appserver_nginx_config(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    try:
        yield "Connecting to appserver {} to update Nginx config".format(appserver)

        appserver_open_http_request(
            appserver,
            "/sites/{}/update-nginx".format(site.id),
            method="POST",
            data={"data": json.dumps(site.serialize_for_appserver())},
            timeout=60,
        )
    except AppserverProtocolError:
        # If an error occurs, disable the Nginx config
        yield "Error updating Nginx config"

        yield "Disabling site Nginx config"
        appserver_open_http_request(
            appserver, "/sites/{}/disable-nginx".format(site.id), method="POST", timeout=120,
        )

        yield "Re-raising exception"
        raise
    else:
        # Success; try to reload
        yield "Successfully updated Nginx config"

        yield "Reloading Nginx config on all appservers"
        try:
            for i in scope["pingable_appservers"]:
                yield "Reloading Nginx config on appserver {}".format(i)

                appserver_open_http_request(
                    i, "/sites/reload-nginx", method="POST", timeout=120,
                )
        except AppserverProtocolError:
            # Error reloading; disable config
            # We're probably fine not reloading Nginx
            yield "Error reloading Nginx config"

            yield "Disabling site Nginx config"
            appserver_open_http_request(
                appserver, "/sites/{}/disable-nginx".format(site.id), method="POST", timeout=120,
            )

            yield "Re-raising exception"
            raise
        else:
            # Everything succeeded!
            yield "Successfully reloaded confgiration"


def update_docker_service(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    yield "Connecting to appserver {} to create/update Docker service".format(appserver)
    appserver_open_http_request(
        appserver,
        "/sites/{}/update-docker-service".format(site.id),
        method="POST",
        data={"data": json.dumps(site.serialize_for_appserver())},
    )

    yield "Created/updated Docker service"


def restart_docker_service(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    yield "Connecting to appserver {} to restart Docker service".format(appserver)
    appserver_open_http_request(
        appserver, "/sites/{}/restart-docker-service".format(site.id), method="POST",
    )

    yield "Restarted Docker service"


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
