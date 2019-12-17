# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import urllib.parse


def split_domain(url: str) -> str:
    domain = urllib.parse.urlsplit(url).netloc

    if ":" in domain:
        domain = domain[: domain.find(":")]

    return domain
