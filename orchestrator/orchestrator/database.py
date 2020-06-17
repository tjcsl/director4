# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import string
from contextlib import contextmanager
from typing import Any, ContextManager, Dict, Optional

import MySQLdb
import psycopg2
from psycopg2 import sql as psql


def mysql_clean_identifier(identifier: str) -> str:
    return "".join(c for c in identifier if c in string.ascii_letters + string.digits + "_")


@contextmanager
def _open_cursor(
    *, dbms: str, hostname: str, port: int, username: str, password: str, dbname: Optional[str]
) -> Any:
    """Opens a cursor to the specified database host. Intended to be used as a context manager.

    This will return different types depending on the value of dbms,
    so make sure to check that before you try to run queries!

    """

    if dbms == "postgres":
        conn = psycopg2.connect(
            host=hostname, port=port, user=username, password=password, dbname=dbname,
        )

        try:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            yield conn.cursor()
        finally:
            conn.close()
    elif dbms == "mysql":
        # For MySQL, we need to indicate Unix sockets specially
        kwargs = {}
        if hostname.startswith("/"):
            kwargs["unix_socket"] = hostname
            hostname = "localhost"

        conn = MySQLdb.connect(
            host=hostname, port=port, user=username, passwd=password, db=dbname, **kwargs,
        )

        try:
            yield conn.cursor()
        finally:
            conn.close()
    else:
        raise ValueError("Unknown DBMS {!r}".format(dbms))


def open_admin_cursor(host_info: Dict[str, Any], dbname: str) -> ContextManager[Any]:
    """Opens a cursor to the specified database host as an administrator, connecting to the
    specified database. Intended to be used as a context manager.

    This will return different types depending on the value of host.dbms,
    so make sure to check that before you try to run queries!

    """

    return _open_cursor(
        dbms=host_info["dbms"],
        hostname=host_info["admin_hostname"],
        port=host_info["admin_port"],
        username=host_info["admin_username"],
        password=host_info["admin_password"],
        dbname=dbname,
    )


def open_site_cursor(database_info: Dict[str, Any]) -> ContextManager[Any]:
    """Opens a cursor to database represented by the serialized Database object information.
    Intended to be used as a context manager.

    This will return different types depending on the value of database_info["db_type"],
    so make sure to check that before you try to run queries!

    """

    return _open_cursor(
        dbms=database_info["db_type"],
        hostname=database_info["host"]["admin_hostname"],
        port=database_info["host"]["admin_port"],
        username=database_info["username"],
        password=database_info["password"],
        dbname=database_info["db_name"],
    )


def create_database(database_info: Dict[str, Any]) -> None:
    if database_info["db_type"] == "postgres":
        with open_admin_cursor(database_info["host"], dbname="postgres") as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_user WHERE usename = %s", (database_info["username"],)
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    psql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                        psql.Identifier(database_info["username"])
                    ),
                    (database_info["password"],),
                )
            else:
                cursor.execute(
                    psql.SQL("ALTER USER {} WITH PASSWORD %s").format(
                        psql.Identifier(database_info["username"])
                    ),
                    (database_info["password"],),
                )

            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (database_info["db_name"],)
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    psql.SQL("CREATE DATABASE {} WITH OWNER = %s").format(
                        psql.Identifier(database_info["db_name"])
                    ),
                    (database_info["host"]["admin_username"],),
                )
            cursor.execute(
                psql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    psql.Identifier(database_info["db_name"]),
                    psql.Identifier(database_info["username"]),
                )
            )

            cursor.execute(
                psql.SQL("GRANT ALL ON SCHEMA public TO {}").format(
                    psql.Identifier(database_info["username"])
                )
            )
    elif database_info["db_type"] == "mysql":
        with open_admin_cursor(database_info["host"], dbname="mysql") as cursor:
            cursor.execute(
                "SELECT 1 FROM mysql.user WHERE user = %s;",
                (mysql_clean_identifier(database_info["username"]),),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "CREATE USER '{}'@'%%' IDENTIFIED BY %s;".format(
                        mysql_clean_identifier(database_info["username"])
                    ),
                    (database_info["password"],),
                )
            else:
                cursor.execute(
                    "SET PASSWORD FOR {}@'%%' = PASSWORD(%s);".format(
                        mysql_clean_identifier(database_info["username"])
                    ),
                    (database_info["password"],),
                )

            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS {}".format(
                    mysql_clean_identifier(database_info["db_name"])
                )
            )
            cursor.execute(
                "GRANT ALL ON {} . * TO {};".format(
                    mysql_clean_identifier(database_info["db_name"]),
                    mysql_clean_identifier(database_info["username"]),
                )
            )

            cursor.execute("FLUSH PRIVILEGES;")
    else:
        raise ValueError("Unknown DBMS {!r}".format(database_info["db_type"]))


def delete_database(database_info: Dict[str, Any]) -> None:
    if database_info["db_type"] == "postgres":
        with open_admin_cursor(database_info["host"], dbname="postgres") as cursor:
            cursor.execute(
                psql.SQL("DROP DATABASE IF EXISTS {}").format(
                    psql.Identifier(database_info["db_name"])
                )
            )

            cursor.execute(
                psql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(
                    psql.Identifier(database_info["username"])
                )
            )
            cursor.execute(
                psql.SQL("DROP USER IF EXISTS {}").format(
                    psql.Identifier(database_info["username"])
                )
            )
    elif database_info["db_type"] == "mysql":
        with open_admin_cursor(database_info["host"], dbname="mysql") as cursor:
            cursor.execute(
                "DROP DATABASE IF EXISTS {};".format(
                    mysql_clean_identifier(database_info["db_name"])
                )
            )

            cursor.execute(
                "DROP USER IF EXISTS {}@'%%';".format(
                    mysql_clean_identifier(database_info["username"])
                )
            )
    else:
        raise ValueError("Unknown DBMS {!r}".format(database_info["db_type"]))


def run_single_query(database_info: Dict[str, Any], sql: str) -> str:
    with open_site_cursor(database_info) as cursor:
        try:
            cursor.execute(sql)
        except psycopg2.DatabaseError as ex:
            return str(ex)
        else:
            if cursor.description is None:
                return ""
            else:
                result = "\t".join(column.name for column in cursor.description)
                for row in cursor:
                    result += "\n" + "\t".join(map(str, row))

                return result
