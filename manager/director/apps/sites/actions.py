# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
from typing import Any, Dict, Iterator, Tuple, Union

from ...utils.appserver import appserver_open_http_request, iter_pingable_appservers
from ...utils.balancer import balancer_open_http_request, iter_pingable_balancers
from .models import Site


def update_appserver_nginx_config(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging appservers"
    pingable_appservers = list(iter_pingable_appservers())
    yield "Pingable appservers: {}".format(pingable_appservers)

    for i in pingable_appservers:
        yield "Updating appserver {}".format(i)
        appserver_open_http_request(
            i,
            "/sites/{}/update-nginx".format(site.id),
            params={"data": json.dumps(site.serialize_for_appserver())},
        )
        yield "Updated appserver {}".format(i)


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
