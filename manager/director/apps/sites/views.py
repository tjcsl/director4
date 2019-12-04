# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Site


@login_required
def index_view(request: HttpRequest) -> HttpResponse:
    show_all = request.user.is_superuser and bool(request.GET.get("all"))

    sites = list(Site.objects.filter(users=request.user).order_by("name"))
    if show_all:
        sites.extend(Site.objects.exclude(users=request.user).order_by("name"))

    context = {
        "show_all": show_all,
        "sites": sites,
    }
    return render(request, "sites/list.html", context)


# Used for routes that do not have views written but need to be linked to
@login_required
def dummy_view(  # pylint: disable=unused-argument
    request: HttpRequest, site_id: Optional[int] = None
) -> HttpResponse:
    return HttpResponse("")


@login_required
def info_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site, id=site_id)
    context = {"site": site}
    return render(request, "sites/info.html", context)
