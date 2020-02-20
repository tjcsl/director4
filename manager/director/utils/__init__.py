# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import urllib.parse


def split_domain(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or ""
