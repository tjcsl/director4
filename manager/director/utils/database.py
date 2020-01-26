# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from contextlib import contextmanager
from typing import Any

import MySQLdb
import psycopg2

from ..apps.sites.models import DatabaseHost


@contextmanager
def open_cursor(host: DatabaseHost, dbname: str) -> Any:
    """Opens a cursor to the specified database host, connecting to the
    specified database. Intended to be used as a context manager.

    This will return different types depending on the value of host.dbms,
    so make sure to check that before you try to run queries!

    """
    if host.dbms == "postgres":
        conn = psycopg2.connect(
            host=host.hostname,
            port=host.port,
            user=host.admin_username,
            password=host.admin_password,
            dbname=dbname,
        )

        try:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            yield conn.cursor()
        finally:
            conn.close()
    elif host.dbms == "mysql":
        conn = MySQLdb.connect(
            host=host.hostname,
            port=host.port,
            user=host.admin_username,
            passwd=host.admin_password,
            db=dbname,
        )

        try:
            yield conn.cursor()
        finally:
            conn.close()
    else:
        raise ValueError("Unknown DBMS {!r}".format(host.dbms))
