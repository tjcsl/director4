# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from ..models import Action, Operation


def prometheus_metrics_view(request: HttpRequest) -> HttpResponse:
    remote_addr = (
        request.META["HTTP_X_REAL_IP"]
        if "HTTP_X_REAL_IP" in request.META
        else request.META.get("REMOTE_ADDR", "")
    )

    if (
        request.user.is_authenticated and request.user.is_superuser
    ) or remote_addr in settings.ALLOWED_METRIC_SCRAPE_IPS:
        metrics = {"director4_sites_failed_actions": Action.objects.filter(result=False).count()}

        return render(
            request, "prometheus-metrics.txt", {"metrics": metrics}, content_type="text/plain"
        )
    else:
        raise Http404


@login_required
def operations_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_superuser:
        raise Http404

    if request.GET.get("failed"):
        title = "Failed Operations"
        failed_only = True
        operation_objs = Operation.objects.filter(action__result=False).distinct()
    else:
        title = "Operations"
        failed_only = False
        operation_objs = Operation.objects.all()

    context = {
        "title": title,
        "failed_only": failed_only,
        "operations": operation_objs,
    }

    return render(request, "sites/operations.html", context)
