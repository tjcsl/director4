# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
from typing import Any, Dict, List

from directorutil.crypto import import_rsa_key_from_file

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

# Maxiumum amount of time to keep the site terminal open without receiving a heartbeat
SITE_TERMINAL_KEEPALIVE_TIMEOUT = 6 * 60 * 60

SHELL_SIGNING_TOKEN_PUBLIC_KEY_PATH = "/etc/director-shell-keys/shell-signing-token-pubkey.pem"
SHELL_ENCRYPTION_TOKEN_PRIVATE_KEY_PATH = (
    "/etc/director-shell-keys/shell-encryption-token-privkey.pem"
)

# Maximum amount of time that a single terminal connection (though the web interface or
# the shell server) can remain open
SHELL_TERMINAL_MAX_LIFETIME: int = 3 * 3600

# Maximum size of files downloadable from & uploadable
# to the orchestrator
MAX_FILE_DOWNLOAD_BYTES = 100 * 1000 * 1000  # 100MB

MAX_FILE_UPLOAD_BYTES = 100 * 1000 * 1000  # 100MB

# No more than this many files in a zip file
# Each file is also limited to MAX_FILE_DOWNLOAD_BYTES
MAX_ZIP_FILES = 1000

# Size of individual chunks
FILE_STREAM_BUFSIZE = 4096

TIMEZONE = "America/New_York"

# The path to the terminal keepalive program
# Here, it is set to None, and is defined in secret.py
# If set to None, it will use a sh script instead of a C program
TERMINAL_KEEPALIVE_PROGRAM_PATH = None

# Logging configuration
LOG_LEVEL = logging.INFO
LOG_FILE = None
LOG_FILE_ROTATE_SIZE = 10 * 1000 * 1000  # Rotate at 10M
LOG_FILE_MAX_BACKUPS = 10

FLASK_CONFIG: Dict[str, Any] = {}

TMP_TMPFS_SIZE = 10 * 1000 * 1000  # 10 MB
RUN_TMPFS_SIZE = 10 * 1000 * 1000  # 10 MB

try:
    from .secret import *  # noqa
except ImportError:
    pass

FLASK_CONFIG.setdefault("MAX_CONTENT_LENGTH", MAX_FILE_UPLOAD_BYTES)

SHELL_SIGNING_TOKEN_PUBLIC_KEY = import_rsa_key_from_file(SHELL_SIGNING_TOKEN_PUBLIC_KEY_PATH)
SHELL_ENCRYPTION_TOKEN_PRIVATE_KEY = import_rsa_key_from_file(
    SHELL_ENCRYPTION_TOKEN_PRIVATE_KEY_PATH
)
