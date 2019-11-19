# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict

from django.conf import settings
from django.http import HttpRequest


def base_context(request: HttpRequest) -> Dict[str, Any]:
    return {
        "DJANGO_SETTINGS": settings,
    }
