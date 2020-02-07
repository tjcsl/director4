# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .. import operations
from ..forms import DatabaseCreateForm
from ..models import Site


@login_required
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
