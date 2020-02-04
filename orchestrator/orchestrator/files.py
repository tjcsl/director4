# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import subprocess

from . import settings


def get_site_directory_path(site_id: int) -> str:
    id_parts = ("{:02d}".format(site_id // 100), "{:02d}".format(site_id % 100))

    return os.path.join(settings.SITES_DIRECTORY, *id_parts)


def ensure_site_directories_exist(site_id: int) -> None:
    site_dir = get_site_directory_path(site_id)

    directories = [
        site_dir,
        os.path.join(site_dir, "private"),
        os.path.join(site_dir, "public"),
    ]

    subprocess.run(
        [
            *settings.SITE_DIRECTORY_COMMAND_PREFIX,
            "/bin/sh",
            "-c",
            'set -e; for fname in "$@"; do mkdir -p -- "$fname"; chmod 0755 -- "$fname"; done',
            "/bin/sh",
            *directories,
        ],
        stdin=subprocess.DEVNULL,
        check=True,
    )
