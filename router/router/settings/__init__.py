# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging

NGINX_DIRECTOR_DIR = "/etc/nginx/director.d"

NGINX_RELOAD_COMMAND = ["sudo", "systemctl", "reload", "nginx"]

HELPER_SCRIPT_EXEC_ARGS = ["sudo", "/usr/bin/python3", "/usr/local/bin/certbot-director"]

SITES_DOMAIN = "sites.tjhsst.edu"

# Logging configuration
LOG_LEVEL = logging.INFO
LOG_FILE = None
LOG_FILE_ROTATE_SIZE = 10 * 1000 * 1000  # Rotate at 10M
LOG_FILE_MAX_BACKUPS = 10
