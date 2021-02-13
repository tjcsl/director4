# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ...auth.decorators import (
    require_accept_guidelines,
    require_accept_guidelines_no_redirect,
    superuser_required,
)
from .. import operations
from ..forms import SiteAvailabilityForm, SiteResourceLimitsForm
from ..models import Action, Operation, Site, SiteResourceLimits

# WARNING: Allowing non-superusers to access ANY of the views here presents a major security
# vulnerability!


@require_accept_guidelines_no_redirect
def prometheus_metrics_view(request: HttpRequest) -> HttpResponse:
    remote_addr = (
        request.META["HTTP_X_REAL_IP"]
        if "HTTP_X_REAL_IP" in request.META
        else request.META.get("REMOTE_ADDR", "")
    )

    if (
        request.user.is_authenticated and request.user.is_superuser
    ) or remote_addr in settings.ALLOWED_METRIC_SCRAPE_IPS:
        metrics = {
            "director4_sites_failed_actions": Action.objects.filter(
                result=False,
                user_recoverable=False,
            ).count(),
        }

        return render(
            request, "prometheus-metrics.txt", {"metrics": metrics}, content_type="text/plain"
        )
    else:
        raise Http404


@superuser_required
@require_accept_guidelines
def management_view(request: HttpRequest) -> HttpResponse:
    return render(request, "sites/management/management.html")


@superuser_required
@require_accept_guidelines
def operations_view(request: HttpRequest) -> HttpResponse:
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

    return render(request, "sites/management/operations.html", context)


@superuser_required
@require_accept_guidelines
def operation_delete_fix_view(request: HttpRequest, operation_id: int) -> HttpResponse:
    operation = Operation.objects.get(id=operation_id)
    site = operation.site

    if not operation.has_failed:
        messages.error(request, "Can only delete failed operations")
        return redirect("sites:operations")

    operation.action_set.all().delete()
    operation.delete()

    operations.fix_site(site)
    return redirect("sites:operations")


@superuser_required
@require_accept_guidelines
def custom_resource_limits_list_view(request: HttpRequest) -> HttpResponse:
    sites_with_custom_limits = SiteResourceLimits.objects.filter_has_custom_limits()  # type: ignore

    context = {
        "custom_limit_sites": [
            Site.objects.get(id=site_id)
            for site_id in sites_with_custom_limits.values_list("site_id", flat=True)
        ],
    }

    return render(request, "sites/management/custom_resource_limits_list.html", context)


@superuser_required
@require_accept_guidelines
def resource_limits_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = Site.objects.get(id=site_id)

    if request.method == "POST":
        form = SiteResourceLimitsForm(request.POST)

        if site.has_operation:
            messages.error(request, "An operation is already being performed on this site")
        else:
            if form.is_valid():
                operations.update_resource_limits(
                    site,
                    form.cleaned_data["cpus"],
                    form.cleaned_data["mem_limit"],
                    form.cleaned_data["client_body_limit"],
                    form.cleaned_data["notes"],
                )

                if "next" in request.GET:
                    return redirect(request.GET["next"])

                return redirect("sites:info", site.id)
    else:
        initial_data = {}
        if SiteResourceLimits.objects.filter(site=site).exists():
            initial_data = {
                "cpus": site.resource_limits.cpus,
                "mem_limit": site.resource_limits.mem_limit,
                "client_body_limit": site.resource_limits.client_body_limit,
                "notes": site.resource_limits.notes,
            }

        form = SiteResourceLimitsForm(initial=initial_data)

    context = {"site": site, "form": form}

    return render(request, "sites/management/resource_limits.html", context)


@superuser_required
@require_accept_guidelines
def availability_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = Site.objects.get(id=site_id)

    if request.method == "POST":
        form = SiteAvailabilityForm(request.POST)

        if site.has_operation:
            messages.error(request, "An operation is already being performed on this site")
        else:
            if form.is_valid():
                operations.update_availability(
                    site,
                    form.cleaned_data["availability"],
                )

                if "next" in request.GET:
                    return redirect(request.GET["next"])

                return redirect("sites:info", site.id)
    else:
        form = SiteAvailabilityForm(initial={"availability": site.availability})

    context = {"site": site, "form": form}

    return render(request, "sites/management/availability.html", context)
