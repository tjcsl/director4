# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..sites import views as sites_views


def index_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return sites_views.index_view(request)
    else:
        return login_view(request)


def login_view(request: HttpRequest) -> HttpResponse:
    return render(request, "auth/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("auth:index")
