# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os

from channels.routing import get_default_application

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "director.settings")
django.setup()
application = get_default_application()
