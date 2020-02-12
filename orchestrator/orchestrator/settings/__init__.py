# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import List

DEBUG = True

SITES_DOMAIN = "sites.tjhsst.edu"

NGINX_CONFIG_DIRECTORY = "/etc/nginx/director.d"

NGINX_SERVICE_NAME = "director-nginx"

# Main data directory
DATA_DIRECTORY = "/data"
# Where site files are stored
SITES_DIRECTORY = "/data/sites"

# The prefix to add to commands being run to operate on files in SITES_DIRECTORY
SITE_DIRECTORY_COMMAND_PREFIX: List[str] = []

SITE_TERMINAL_KEEPALIVE_TIMEOUT = 6 * 60 * 60

# Keep this low because files are not streamed
MAX_FILE_DOWNLOAD_BYTES = 10 * 1000 * 1000  # 10MB

TIMEZONE = "America/New_York"

try:
    from .secret import *  # noqa
except ImportError:
    pass
