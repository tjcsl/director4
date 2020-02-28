# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from ....utils.appserver import (
    AppserverProtocolError,
    appserver_open_http_request,
    iter_random_pingable_appservers,
)
from ..models import Site


@require_GET
@login_required
def get_file_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)

    path = request.GET["path"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        res = appserver_open_http_request(
            appserver,
            "/sites/{}/files/get".format(site.id),
            method="GET",
            params={"path": path},
            timeout=10,
        )
    except AppserverProtocolError:
        return HttpResponse(status=500)

    text = res.text

    return HttpResponse(text, content_type="text/plain")


@require_POST
@login_required
def remove_file_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)

    path = request.GET["path"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/remove".format(site.id),
            method="POST",
            params={"path": path},
            timeout=10,
        )
    except AppserverProtocolError:
        return HttpResponse(status=500)

    return HttpResponse("Sucess", content_type="text/plain")


@require_POST
@login_required
def remove_directory_recur_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)

    path = request.GET["path"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/rmdir-recur".format(site.id),
            method="POST",
            params={"path": path},
            timeout=10,
        )
    except AppserverProtocolError:
        return HttpResponse(status=500)

    return HttpResponse("Success", content_type="text/plain")


@require_POST
@login_required
def make_directory_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)

    path = request.GET["path"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/mkdir".format(site.id),
            method="POST",
            params={"path": path, "mode": request.GET.get("mode", "")},
            timeout=10,
        )
    except AppserverProtocolError:
        return HttpResponse(status=500)

    return HttpResponse("Success", content_type="text/plain")


@require_POST
@login_required
def chmod_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)
    if "mode" not in request.GET:
        return HttpResponse(status=400)

    path = request.GET["path"]
    mode = request.GET["mode"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/chmod".format(site.id),
            method="POST",
            params={"path": path, "mode": mode},
            timeout=10,
        )
    except AppserverProtocolError:
        return HttpResponse(status=500)

    return HttpResponse("Success", content_type="text/plain")
