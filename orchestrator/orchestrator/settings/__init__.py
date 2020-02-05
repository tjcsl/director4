from typing import List

DEBUG = True

SITES_DOMAIN = "sites.tjhsst.edu"

NGINX_CONFIG_DIRECTORY = "/etc/nginx/director.d"

# Will be run by the orchestrator to check the Nginx config for errors. stdout/stderr are discarded
# -- only the return code is checked.
NGINX_CONFIG_CHECK_COMMAND = ["sudo", "-u", "root", "nginx", "-t"]

# Will be run by the orchestrator to reload the Nginx config. stdout/stderr are discarded
# -- only the return code is checked.
NGINX_CONFIG_RELOAD_COMMAND = ["docker", "service", "update", "--force", "director-nginx"]

# Main data directory
DATA_DIRECTORY = "/data"
# Where site files are stored
SITES_DIRECTORY = "/data/sites"

# The prefix to add to commands being run to operate on files in SITES_DIRECTORY
SITE_DIRECTORY_COMMAND_PREFIX: List[str] = []

SITE_TERMINAL_KEEPALIVE_TIMEOUT = 6 * 60 * 60

try:
    from .secret import *  # noqa
except ImportError:
    pass
