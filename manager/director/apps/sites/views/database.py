# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ....utils.appserver import appserver_open_http_request, iter_random_pingable_appservers
from ...auth.decorators import require_accept_guidelines
from .. import operations
from ..forms import DatabaseCreateForm
from ..models import Site


@login_required
@require_accept_guidelines
def create_database_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if site.database is not None:
        return redirect("sites:info", site.id)

    if request.method == "POST":
        form = DatabaseCreateForm(request.POST)
        if site.has_operation:
            messages.error(request, "An operation is already being performed on this site")
        elif form.is_valid():
            operations.create_database(site, form.cleaned_data["host"])
            return redirect("sites:info", site.id)
    else:
        form = DatabaseCreateForm()

    context = {"site": site, "form": form}

    return render(request, "sites/databases/create.html", context)


@login_required
@require_accept_guidelines
def delete_database_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    if request.method == "POST":
        if request.POST.get("confirm") == site.name:
            operations.delete_database(site)
            return redirect("sites:info", site.id)

    return render(request, "sites/databases/delete.html", {"site": site})


@login_required
@require_accept_guidelines
def database_shell_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if site.database is None:
        return redirect("sites:info", site.id)

    if request.method == "POST":
        sql = request.POST.get("sql")
        if sql:
            try:
                appserver_num = next(iter(iter_random_pingable_appservers()))
            except StopIteration:
                return HttpResponse("", content_type="text/plain", status=500)

            res = appserver_open_http_request(
                appserver_num,
                "/sites/databases/query",
                method="POST",
                data={
                    "database_info": json.dumps(site.database.serialize_for_appserver()),
                    "sql": sql,
                },
                timeout=30,
            )

            return HttpResponse(res.text, content_type="text/plain")
        else:
            return HttpResponse("", content_type="text/plain")

    return render(request, "sites/databases/shell.html", {"site": site})
