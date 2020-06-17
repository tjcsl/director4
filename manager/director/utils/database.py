# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json

from ..apps.sites.models import Database
from .appserver import appserver_open_http_request, iter_random_pingable_appservers


def create_database(database: Database) -> None:
    appserver_num = next(iter(iter_random_pingable_appservers()))

    appserver_open_http_request(
        appserver_num,
        "/sites/databases/create",
        method="POST",
        data={"data": json.dumps(database.serialize_for_appserver())},
        timeout=30,
    )


def delete_database(database: Database) -> None:
    appserver_num = next(iter(iter_random_pingable_appservers()))

    appserver_open_http_request(
        appserver_num,
        "/sites/databases/delete",
        method="POST",
        data={"data": json.dumps(database.serialize_for_appserver())},
        timeout=30,
    )
