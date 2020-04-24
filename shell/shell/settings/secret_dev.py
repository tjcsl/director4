# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os

SERVER_HOST_KEY_FILES = [
    os.path.join("/etc/director-shell-keys/etc/ssh", "ssh_host_{}_key".format(name))
    for name in ["rsa", "dsa", "ecdsa", "ed25519"]
]

MANAGER_HOST = "localhost:8080"
MANAGER_SSL = None

APPSERVER_WS_HOSTS = ["localhost:5010"]
APPSERVER_SSL = None
