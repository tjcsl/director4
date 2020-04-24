# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, List, Optional

from directorutil.ssl_context import create_internal_client_ssl_context

SERVER_HOST_KEY_FILES: List[str] = []

# This is a "host:port" combo.
# Example: "localhost:6143"
MANAGER_HOST: str = ""

# Set this to None to disable SSL. Set it to a dictionary like this to enable SSL:
# {
#     "cafile": "<path to CA file used to verify appserver certificates>",
#     "client_cert": {
#         "certfile": "<path to client certificate file>",  # Required
#         "keyfile": "<path to client private key file>",  # Taken from certfile
#         # if not passed
#         "password": "<private key password>",  # Required if private key is
#         # encrypted
#     },
# }
MANAGER_SSL: Optional[Dict[str, Any]] = None

# These are "host:port" combos.
# Example: ["localhost:6243", "director-app1.example.com:6243"]
APPSERVER_WS_HOSTS: List[str] = []

# See MANAGER_SSL.
# The SSL settings must be the same for all appservers. This is by design.
APPSERVER_SSL: Optional[Dict[str, Any]] = None

try:
    from .secret import *  # noqa # pylint: disable=wildcard-import
except ImportError:
    pass

assert MANAGER_HOST, "MANAGER_HOST must be set"
assert APPSERVER_WS_HOSTS, "APPSERVER_WS_HOSTS must be set"

MANAGER_SSL_CONTEXT = create_internal_client_ssl_context(MANAGER_SSL)
APPSERVER_SSL_CONTEXT = create_internal_client_ssl_context(APPSERVER_SSL)
