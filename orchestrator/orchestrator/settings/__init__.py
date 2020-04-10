# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
from typing import List

# Should be set to False in production
DEBUG = True

SITES_DOMAIN = "sites.tjhsst.edu"

# Location of nginx configs in containers
NGINX_CONFIG_DIRECTORY = "/data/nginx/director.d"

# Name of Nginx Docker Swarm service
NGINX_SERVICE_NAME = "director-nginx"

# Registry URL
DOCKER_REGISTRY_URL = "localhost:4433"

# Mapping of username to password for authentication to
# registry
DOCKER_REGISTRY_AUTH_CONFIG = {"username": "user", "password": "user"}

# Maximum length of time for requests to Docker registry
# API
DOCKER_REGISTRY_TIMEOUT = 20

# "Maintainer" of custom docker images
DOCKER_IMAGE_MAINTAINER = "CSL"

# Main data directory
DATA_DIRECTORY = "/data"
# Where site files are stored
# This should be owned by the user/group that Docker containers run as
# (root by default, or the `userns-remap` user; see
# https://docs.docker.com/engine/security/userns-remap/)
# The permissions on this directory MUST be AT LEAST 770, preferably
# more restrictive (700 is best).
SITES_DIRECTORY = "/data/sites"
# Where image Dockerifles are stored
DOCKERFILE_DIRECTORY = "/data/images"

# See docs/UMASK.md before touching this
# MAKE SURE TO INCLUDE THE "0o" PREFIX!
SITE_UMASK: int = 0o007

# The prefix to add to commands being run to operate on files in SITES_DIRECTORY
SITE_DIRECTORY_COMMAND_PREFIX: List[str] = []

# Maxiumum amount of time to keep the
# site terminal open
SITE_TERMINAL_KEEPALIVE_TIMEOUT = 6 * 60 * 60

# Maximum size of files downloadable from & uploadable
# to the orchestrator
MAX_FILE_DOWNLOAD_BYTES = 10 * 1000 * 1000  # 10MB

MAX_FILE_UPLOAD_BYTES = 10 * 1000 * 1000  # 10MB

# No more than this many files in a zip file
# Each file is also limited to MAX_FILE_DOWNLOAD_BYTES
MAX_ZIP_FILES = 1000

# Size of individual chunks
FILE_STREAM_BUFSIZE = 4096

FLASK_CONFIG = {
    "MAX_CONTENT_LENGTH": MAX_FILE_UPLOAD_BYTES,  # 10MB
}

TIMEZONE = "America/New_York"

# Logging configuration
LOG_LEVEL = logging.INFO
LOG_FILE = None
LOG_FILE_ROTATE_SIZE = 10 * 1000 * 1000  # Rotate at 10M
LOG_FILE_MAX_BACKUPS = 10

try:
    from .secret import *  # noqa
except ImportError:
    pass
