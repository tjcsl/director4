# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import subprocess
from typing import Any, Dict, Iterable

from . import settings


def run_helper(args: Iterable[str], **kwargs: Any) -> "subprocess.CompletedProcess[Any]":
    return subprocess.run(  # pylint: disable=subprocess-run-check
        [*settings.HELPER_SCRIPT_EXEC_ARGS, *args], **kwargs,
    )


def setup(site_id: int, data: Dict[str, Any]) -> None:
    run_helper(["setup", str(site_id), *data["custom_domains"]], check=True)


def remove_old_domains(domains: Iterable[str]) -> None:
    run_helper(["remove-old-domains"], input=(" ".join(domains)).encode(), check=True)
