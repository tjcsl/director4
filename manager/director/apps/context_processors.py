# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict

from django.conf import settings
from django.http import HttpRequest

from .request.models import SiteRequest


def base_context(request: HttpRequest) -> Dict[str, Any]:
    return {
        "DJANGO_SETTINGS": settings,
        "show_teacher_site_request_button": (
            request.user.is_authenticated
            and request.user.is_teacher
            and SiteRequest.objects.filter(teacher=request.user, teacher_approval=None).exists()
        ),
        "show_admin_site_request_button": (
            request.user.is_authenticated
            and request.user.is_superuser
            and SiteRequest.objects.filter(teacher_approval=True, admin_approval=None).exists()
        ),
    }
