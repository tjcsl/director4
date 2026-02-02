# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os

SERVER_HOST_KEY_FILES = [
    path
    for path in (
        os.path.join("/etc/director-shell-keys/etc/ssh", "ssh_host_{}_key".format(name))
        for name in ["rsa", "ecdsa", "ed25519"]
    )
    if os.path.exists(path)
]

MANAGER_HOST = "localhost:8080"
MANAGER_SSL = None

APPSERVER_WS_HOSTS = ["localhost:5010"]
APPSERVER_SSL = None
