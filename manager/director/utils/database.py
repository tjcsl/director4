# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import string
from contextlib import contextmanager
from typing import Any, Optional

import MySQLdb
import psycopg2
from psycopg2 import sql as psql

from ..apps.sites.models import Database, DatabaseHost


def mysql_clean_identifier(identifier: str) -> str:
    return "".join(c for c in identifier if c in string.ascii_letters + string.digits + "_")


@contextmanager
def open_cursor(host: DatabaseHost, dbname: Optional[str]) -> Any:
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


def create_database(database: Database) -> None:
    if database.host.dbms == "postgres":
        with open_cursor(database.host, dbname="postgres") as cursor:
            cursor.execute("SELECT 1 FROM pg_catalog.pg_user WHERE usename = %s", (database.username,))
            if cursor.rowcount == 0:
                cursor.execute(
                    psql.SQL("CREATE USER {} WITH PASSWORD %s").format(psql.Identifier(database.username)), (database.password,)
                )
            else:
                cursor.execute(
                    psql.SQL("ALTER USER {} WITH PASSWORD %s").format(psql.Identifier(database.username)), (database.password,)
                )

            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database.db_name,))
            if cursor.rowcount == 0:
                cursor.execute(
                    psql.SQL("CREATE DATABASE {} WITH OWNER = %s").format(psql.Identifier(database.db_name)),
                    (database.host.admin_username,),
                )
            cursor.execute(
                psql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(psql.Identifier(database.db_name), psql.Identifier(database.username))
            )

            cursor.execute(psql.SQL("GRANT ALL ON SCHEMA public TO {}").format(psql.Identifier(database.username)))
    elif database.host.dbms == "mysql":
        with open_cursor(database.host, dbname="mysql") as cursor:
            cursor.execute("SELECT 1 FROM mysql.user WHERE user = %s;", (mysql_clean_identifier(database.username),))
            if cursor.rowcount == 0:
                cursor.execute(
                    "CREATE USER '{}'@'%%' IDENTIFIED BY %s;".format(mysql_clean_identifier(database.username)), (database.password,)
                )
            else:
                cursor.execute(
                    "SET PASSWORD FOR {}@'%%' = PASSWORD(%s);".format(mysql_clean_identifier(database.username)), (database.password,)
                )

            cursor.execute("CREATE DATABASE IF NOT EXISTS {}".format(mysql_clean_identifier(database.db_name)))
            cursor.execute("GRANT ALL ON {} . * TO {};".format(mysql_clean_identifier(database.db_name), mysql_clean_identifier(database.username)))

            cursor.execute("FLUSH PRIVILEGES;")
    else:
        raise ValueError("Unknown DBMS {!r}".format(database.host.dbms))


def update_password(database: Database) -> None:
    if database.host.dbms == "postgres":
        with open_cursor(database.host, dbname="postgres") as cursor:
            cursor.execute(psql.SQL("ALTER USER {} WITH PASSWORD %s").format(psql.Identifier(database.username)), (database.password,))
    elif database.host.dbms == "mysql":
        with open_cursor(database.host, dbname="mysql") as cursor:
            cursor.execute(
                "SET PASSWORD FOR {}@'%%' = PASSWORD(%s);".format(mysql_clean_identifier(database.username)), (database.password,)
            )

            cursor.execute("FLUSH PRIVILEGES;")
    else:
        raise ValueError("Unknown DBMS {!r}".format(database.host.dbms))


def delete_database(database: Database) -> None:
    if database.host.dbms == "postgres":
        with open_cursor(database.host, dbname="postgres") as cursor:
            cursor.execute(psql.SQL("DROP DATABASE IF EXISTS {}").format(psql.Identifier(database.db_name)))

            cursor.execute(psql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(psql.Identifier(database.username)))
            cursor.execute(psql.SQL("DROP USER IF EXISTS {}").format(psql.Identifier(database.username)))
    elif database.host.dbms == "mysql":
        with open_cursor(database.host, dbname="mysql") as cursor:
            cursor.execute("DROP DATABASE IF EXISTS {};".format(mysql_clean_identifier(database.db_name)))

            cursor.execute("DROP USER IF EXISTS {}@'%%';".format(mysql_clean_identifier(database.username)))
    else:
        raise ValueError("Unknown DBMS {!r}".format(database.host.dbms))
