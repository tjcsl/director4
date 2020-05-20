# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.apps import AppConfig


class SitesConfig(AppConfig):
    name = "director.apps.sites"

    def ready(self):
        from . import signals  # noqa # pylint: disable=unused-import,import-outside-toplevel
