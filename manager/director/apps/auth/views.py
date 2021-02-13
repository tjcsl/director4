# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import cast

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..sites import views as sites_views
from .decorators import require_accept_guidelines


@require_accept_guidelines
def index_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return cast(HttpResponse, sites_views.sites.index_view(request))
    else:
        return login_view(request)


@login_required
def accept_guidelines_view(request: HttpRequest) -> HttpResponse:
    assert request.user.is_authenticated

    if request.method == "POST":
        if request.POST.get("accepted"):
            request.user.accepted_guidelines = True
            request.user.save(update_fields=["accepted_guidelines"])

    if request.user.accepted_guidelines:
        return redirect("auth:index")

    return render(request, "auth/accept_guidelines.html")


def login_view(request: HttpRequest) -> HttpResponse:
    return render(request, "auth/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("auth:index")
