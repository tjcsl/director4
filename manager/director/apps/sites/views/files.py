# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

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
        raise Exception("No appservers online")

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
