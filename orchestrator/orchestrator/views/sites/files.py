# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import traceback
from typing import Tuple, Union

from flask import Blueprint, current_app, request

from ... import settings
from ...files import (
    SiteFilesException,
    get_site_file,
    remove_all_site_files_dangerous,
    write_site_file,
)
from ...utils import iter_chunks

files = Blueprint("files", __name__)


@files.route("/sites/<int:site_id>/files/get", methods=["GET"])
def get_file_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Get a file from a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        return get_site_file(site_id, request.args["path"])
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/files/write", methods=["POST"])
def write_file_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Write a file to a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        write_site_file(
            site_id,
            request.args["path"],
            iter_chunks(request.stream, settings.FILE_STREAM_BUFSIZE),
            mode_str=request.args.get("mode", None),
        )
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/remove-all-site-files-dangerous", methods=["POST"])
def remove_all_site_files_dangerous_page(site_id: int) -> Union[str, Tuple[str, int]]:
    try:
        remove_all_site_files_dangerous(site_id)
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"
