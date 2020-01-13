DEBUG = True

SITES_DOMAIN = "sites.tjhsst.edu"

# Will be run by the orchestrator to check the Nginx config for errors. stdout/stderr are discarded
# -- only the return code is checked.
NGINX_CONFIG_CHECK_COMMAND = ["sudo", "-u", "root", "nginx", "-t"]

# Will be run by the orchestrator to reload the Nginx config. stdout/stderr are discarded
# -- only the return code is checked.
NGINX_CONFIG_RELOAD_COMMAND = ["sudo", "-u", "root", "systemctl", "reload", "nginx"]
