# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

NGINX_DIRECTOR_DIR = "/etc/nginx/director.d"

NGINX_RELOAD_COMMAND = ["sudo", "systemctl", "reload", "nginx"]

HELPER_SCRIPT_EXEC_ARGS = ["sudo", "/usr/local/bin/certbot-director"]

SITES_DOMAIN = "sites.tjhsst.edu"
