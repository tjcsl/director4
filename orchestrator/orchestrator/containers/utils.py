# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json


def pprint_json(js: dict) -> None:
    """Prints out provided JSON in pretty, indented format.

    Args:
        js: The provided JSON to print
    """
    print(json.dumps(js, indent=4, sort_keys=True))
