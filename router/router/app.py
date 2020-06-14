# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import logging
import logging.handlers
import traceback
from typing import Tuple, Union

from flask import Flask, request

from . import certbot, nginx, settings

app = Flask(__name__)

if settings.LOG_FILE is not None:
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=settings.LOG_FILE_ROTATE_SIZE,
        backupCount=settings.LOG_FILE_MAX_BACKUPS,
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-8s]: %(message)s"))
    file_handler.setLevel(settings.LOG_LEVEL)

    app.logger.addHandler(file_handler)  # pylint: disable=no-member


@app.route("/ping")
def ping_page() -> str:
    return request.args.get("message", "Pong")


@app.route("/sites/<int:site_id>/update-nginx", methods=["POST"])
def update_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Updates the Nginx config for a given site.

    Based on the provided site_id and data, updates
    the Nginx config. Returns "Success" if successful,
    else an appropriate error.
    """

    if "data" not in request.form:
        return "Error", 400

    try:
        nginx.update_config(site_id, json.loads(request.form["data"]))
    except BaseException:  # pylint: disable=broad-except
        app.logger.error("%s", traceback.format_exc())  # pylint: disable=no-member
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/<int:site_id>/remove-nginx", methods=["POST"])
def remove_nginx_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Removes the Nginx config for a given site."""

    try:
        nginx.remove_config(site_id)
    except BaseException:  # pylint: disable=broad-except
        app.logger.error("%s", traceback.format_exc())  # pylint: disable=no-member
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/<int:site_id>/certbot-setup", methods=["POST"])
def setup_certbot_page(site_id: int) -> Union[str, Tuple[str, int]]:
    """Sets up Certbot to renew a given site's custom domains."""

    if "data" not in request.form:
        return "Error", 400

    try:
        certbot.setup(site_id, json.loads(request.form["data"]))
    except BaseException:  # pylint: disable=broad-except
        app.logger.error("%s", traceback.format_exc())  # pylint: disable=no-member
        return "Error", 500
    else:
        return "Success"


@app.route("/sites/certbot-remove-old-domains", methods=["POST"])
def remove_old_certbot_domains_page() -> Union[str, Tuple[str, int]]:
    """Removes now-unused custom domains from Certbot."""

    if "domains" not in request.form:
        return "Error", 400

    try:
        certbot.remove_old_domains(json.loads(request.form["domains"]))
    except BaseException:  # pylint: disable=broad-except
        app.logger.error("%s", traceback.format_exc())  # pylint: disable=no-member
        return "Error", 500
    else:
        return "Success"
