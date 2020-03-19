# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import traceback
from typing import Generator, Tuple, Union

from flask import Blueprint, Response, current_app, request

from .. import settings
from ..files import (
    SiteFilesException,
    chmod_path,
    create_site_file,
    download_zip_site_dir,
    make_site_directory,
    remove_all_site_files_dangerous,
    remove_site_directory_recur,
    remove_site_file,
    rename_path,
    stream_site_file,
    write_site_file,
)
from ..utils import iter_chunks

files = Blueprint("files", __name__)


@files.route("/sites/<int:site_id>/files/get", methods=["GET"])
def get_file_page(site_id: int) -> Union[Tuple[str, int], Response]:
    """Stream a file from a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        stream = stream_site_file(site_id, request.args["path"])

        # Get the first chunk so we can see if there are any errors
        try:
            first_chunk = next(stream)
        except StopIteration:
            # Empty file
            first_chunk = b""
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 400
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:

        def stream_wrapper() -> Generator[bytes, None, None]:
            if first_chunk:
                yield first_chunk

            try:
                yield from stream
            except SiteFilesException:
                pass

        return Response(stream_wrapper(), mimetype="text/plain")


@files.route("/sites/<int:site_id>/files/download-zip", methods=["GET"])
def download_zip_page(site_id: int) -> Union[Tuple[str, int], Response]:
    """Stream a zip file of files from a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        stream = download_zip_site_dir(site_id, request.args["path"])

        # Get the first chunk so we can see if there are any errors
        try:
            first_chunk = next(stream)
        except StopIteration:
            # Empty file
            first_chunk = b""
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:

        def stream_wrapper() -> Generator[bytes, None, None]:
            if first_chunk:
                yield first_chunk

            try:
                yield from stream
            except SiteFilesException:
                pass

        return Response(stream_wrapper(), mimetype="text/plain")


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


@files.route("/sites/<int:site_id>/files/create", methods=["POST"])
def create_file_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Create a file in a site's directory"""

    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        create_site_file(
            site_id, request.args["path"], mode_str=request.args.get("mode", None),
        )
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/files/remove", methods=["POST"])
def remove_file_page(site_id: int) -> Union[str, Tuple[str, int]]:
    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        remove_site_file(site_id, request.args["path"])
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/files/mkdir", methods=["POST"])
def make_directory_page(site_id: int) -> Union[str, Tuple[str, int]]:
    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        make_site_directory(site_id, request.args["path"], mode_str=request.args.get("mode", ""))
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/files/chmod", methods=["POST"])
def chmod_page(site_id: int) -> Union[str, Tuple[str, int]]:
    if "path" not in request.args:
        return "path parameter not passed", 400
    if "mode" not in request.args:
        return "mode parameter not passed", 400

    try:
        chmod_path(site_id, request.args["path"], mode_str=request.args["mode"])
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/files/rename", methods=["POST"])
def rename_page(site_id: int) -> Union[str, Tuple[str, int]]:
    if "oldpath" not in request.args:
        return "oldpath parameter not passed", 400
    if "newpath" not in request.args:
        return "newath parameter not passed", 400

    try:
        rename_path(site_id, request.args["oldpath"], request.args["newpath"])
    except SiteFilesException as ex:
        current_app.logger.error("%s", traceback.format_exc())
        return str(ex), 500
    except BaseException:  # pylint: disable=broad-except
        current_app.logger.error("%s", traceback.format_exc())
        return "Error", 500
    else:
        return "Success"


@files.route("/sites/<int:site_id>/files/rmdir-recur", methods=["POST"])
def remove_directory_recur_page(site_id: int) -> Union[str, Tuple[str, int]]:
    if "path" not in request.args:
        return "path parameter not passed", 400

    try:
        remove_site_directory_recur(site_id, request.args["path"])
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
