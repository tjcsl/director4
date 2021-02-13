# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pulls the latest version of the Director docs"

    def handle(self, *args, **options) -> None:
        subprocess.run(
            ["git", "pull"],
            cwd=settings.DIRECTOR_DOCS_DIR,
            check=True,
        )
