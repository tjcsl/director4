# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
from typing import List

DEBUG = True

SITES_DOMAIN = "sites.tjhsst.edu"

NGINX_CONFIG_DIRECTORY = "/etc/nginx/director.d"

NGINX_SERVICE_NAME = "director-nginx"

STATIC_NGINX_SERVICE_NAME = "director-nginx-static"

STATIC_NGINX_CONFIG_DIRECTORY = "/data/nginx-static/director.d"

DOCKER_REGISTRY_URL = "localhost:4433"

DOCKER_REGISTRY_AUTH_CONFIG = {"username": "user", "password": "user"}

DOCKER_REGISTRY_TIMEOUT = 20

# Main data directory
DATA_DIRECTORY = "/data"
# Where site files are stored
SITES_DIRECTORY = "/data/sites"
# Where image Dockerifles are stored
DOCKERFILE_DIRECTORY = "/data/images"

# The prefix to add to commands being run to operate on files in SITES_DIRECTORY
SITE_DIRECTORY_COMMAND_PREFIX: List[str] = []

SITE_TERMINAL_KEEPALIVE_TIMEOUT = 6 * 60 * 60

MAX_FILE_DOWNLOAD_BYTES = 10 * 1000 * 1000  # 10MB

MAX_FILE_UPLOAD_BYTES = 10 * 1000 * 1000  # 10MB

FILE_STREAM_BUFSIZE = 4096

FLASK_CONFIG = {
    "MAX_CONTENT_LENGTH": MAX_FILE_UPLOAD_BYTES,  # 10MB
}

TIMEZONE = "America/New_York"

LOG_LEVEL = logging.INFO
LOG_FILE = None
LOG_FILE_ROTATE_SIZE = 10 * 1000 * 1000  # Rotate at 10M
LOG_FILE_MAX_BACKUPS = 10

try:
    from .secret import *  # noqa
except ImportError:
    pass
