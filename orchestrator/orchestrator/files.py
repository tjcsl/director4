# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import subprocess

from . import settings


def get_site_directory_path(site_id: int) -> str:
    long_id = "{:04d}".format(site_id)

    id_parts = (long_id[:-2], long_id[-2:])

    return os.path.join(settings.SITES_DIRECTORY, *id_parts)


def ensure_site_directories_exist(site_id: int) -> None:
    site_dir = get_site_directory_path(site_id)

    directories = [
        site_dir,
        os.path.join(site_dir, "private"),
        os.path.join(site_dir, "public"),
    ]

    for directory in directories:
        subprocess.run(
            [*settings.SITE_DIRECTORY_COMMAND_PREFIX, "mkdir", "-p", "--", directory],
            stdin=subprocess.DEVNULL,
            check=True,
        )

        subprocess.run(
            [*settings.SITE_DIRECTORY_COMMAND_PREFIX, "chmod", "0755", "--", directory],
            stdin=subprocess.DEVNULL,
            check=True,
        )
