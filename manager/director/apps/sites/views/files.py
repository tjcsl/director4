# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
from typing import Generator, Union

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from ....utils.appserver import (
    AppserverProtocolError,
    appserver_open_http_request,
    iter_random_pingable_appservers,
)
from ...auth.decorators import require_accept_guidelines, require_accept_guidelines_no_redirect
from ..models import Site


@require_GET
@login_required
@require_accept_guidelines
def editor_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    context = {
        "site": site,
    }

    return render(request, "sites/editor.html", context)


@require_GET
@login_required
@require_accept_guidelines_no_redirect
def get_file_view(request: HttpRequest, site_id: int) -> Union[HttpResponse, StreamingHttpResponse]:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

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
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    def stream() -> Generator[bytes, None, None]:
        while True:
            chunk = res.response.read(4096)
            if not chunk:
                break

            yield chunk

    response = StreamingHttpResponse(stream(), content_type="text/plain")
    response["Content-Type"] = "application/octet-stream"
    response["Content-Disposition"] = "attachment; filename={}".format(os.path.basename(path))

    return response


@require_GET
@login_required
@require_accept_guidelines_no_redirect
def download_zip_view(
    request: HttpRequest, site_id: int
) -> Union[HttpResponse, StreamingHttpResponse]:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

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
            "/sites/{}/files/download-zip".format(site.id),
            method="GET",
            params={"path": path},
            timeout=10,
        )
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    def stream() -> Generator[bytes, None, None]:
        while True:
            chunk = res.response.read(4096)
            if not chunk:
                break

            yield chunk

    response = StreamingHttpResponse(stream(), content_type="application/zip")
    response["Content-Disposition"] = "attachment; filename={}".format(
        os.path.basename(path) + ".zip"
    )

    return response


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def write_file_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    if "path" in request.GET and "contents" in request.POST:
        params = {"path": request.GET["path"]}
        if request.GET.get("mode", ""):
            params["mode"] = request.GET["mode"]

        try:
            appserver_open_http_request(
                appserver,
                "/sites/{}/files/write".format(site.id),
                method="POST",
                params=params,
                data=request.POST["contents"].encode(),
                timeout=600,
            )
        except AppserverProtocolError as ex:
            return HttpResponse(str(ex), status=500)

        return HttpResponse("Success")
    else:
        files = request.FILES.getlist("files[]")
        if not files:
            return HttpResponse(status=400)

        basepath = request.GET.get("basepath") or ""

        for f_obj in files:
            file_name = f_obj.name
            if file_name is None:
                return HttpResponse(status=400)
            try:
                appserver_open_http_request(
                    appserver,
                    "/sites/{}/files/write".format(site.id),
                    method="POST",
                    params={"path": os.path.join(basepath, file_name)},
                    data=f_obj.chunks(),
                    timeout=600,
                )
            except AppserverProtocolError as ex:
                return HttpResponse(str(ex), status=500)

        return HttpResponse("Success")


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def create_file_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    params = {"path": request.GET["path"]}
    if request.GET.get("mode", ""):
        params["mode"] = request.GET["mode"]

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/create".format(site.id),
            method="POST",
            params=params,
            timeout=600,
        )
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    return HttpResponse("Success")


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def remove_file_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

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
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    return HttpResponse("Sucess", content_type="text/plain")


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def remove_directory_recur_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

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
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    return HttpResponse("Success", content_type="text/plain")


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def make_directory_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if "path" not in request.GET:
        return HttpResponse(status=400)

    params = {"path": request.GET["path"]}
    if request.GET.get("mode", ""):
        params["mode"] = request.GET["mode"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/mkdir".format(site.id),
            method="POST",
            params=params,
            timeout=10,
        )
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    return HttpResponse("Success", content_type="text/plain")


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def chmod_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

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
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    return HttpResponse("Success", content_type="text/plain")


@require_POST
@login_required
@require_accept_guidelines_no_redirect
def rename_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if "oldpath" not in request.GET:
        return HttpResponse(status=400)
    if "newpath" not in request.GET:
        return HttpResponse(status=400)

    oldpath = request.GET["oldpath"]
    newpath = request.GET["newpath"]

    try:
        appserver = next(iter_random_pingable_appservers(timeout=0.5))
    except StopIteration:
        return HttpResponse("No appservers online", content_type="text/plain", status=500)

    try:
        appserver_open_http_request(
            appserver,
            "/sites/{}/files/rename".format(site.id),
            method="POST",
            params={"oldpath": oldpath, "newpath": newpath},
            timeout=10,
        )
    except AppserverProtocolError as ex:
        return HttpResponse(str(ex), status=500)

    return HttpResponse("Success", content_type="text/plain")
