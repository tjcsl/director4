# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import traceback
from typing import Tuple, Union

from flask import Blueprint, current_app, request

from .. import database as database_utils

database_blueprint = Blueprint("databases", __name__)


@database_blueprint.route("/sites/databases/create", methods=["POST"])
def create_database_page() -> Union[str, Tuple[str, int]]:
    if "data" not in request.form:
        return "data parameter not passed", 400

    try:
        database_utils.create_database(json.loads(request.form["data"]))
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@database_blueprint.route("/sites/databases/delete", methods=["POST"])
def delete_database_page() -> Union[str, Tuple[str, int]]:
    if "data" not in request.form:
        return "data parameter not passed", 400

    try:
        database_utils.delete_database(json.loads(request.form["data"]))
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@database_blueprint.route("/sites/databases/query", methods=["POST"])
def query_database_page() -> Union[str, Tuple[str, int]]:
    if "database_info" not in request.form:
        return "database_info parameter not passed", 400

    if "sql" not in request.form:
        return "sql parameter not passed", 400

    try:
        return database_utils.run_single_query(
            json.loads(request.form["database_info"]), request.form["sql"]
        )
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
