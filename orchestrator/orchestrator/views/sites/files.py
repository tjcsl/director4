# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import traceback
from typing import Tuple, Union

from flask import Blueprint, request

from ...files import SiteFilesException, get_site_file

files = Blueprint("files", __name__)


@files.route("/sites/<int:site_id>/files/get", methods=["GET"])
def get_file_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Get a file from a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        return get_site_file(site_id, request.args["path"])
    except SiteFilesException as ex:
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        traceback.print_exc()
        return "Error", 500
    else:
        return "Success"
