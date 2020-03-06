# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ...utils.emails import send_email
from .forms import SiteRequestForm

@login_required
def approve_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("")


@login_required
def create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SiteRequestForm(request.POST)
        if form.is_valid():
            site_request = form.save(commit=False)
            site_request.user = request.user
            site_request.save()

            send_email(
                text_template="emails/approve_request.txt",
                html_template="emails/approve_request.html",
                context={"site_request": site_request, "DJANGO_SETTINGS": settings},
                subject="A website request needs your approval",
                emails=[site_request.teacher.email],
            )

            messages.success(request, "Website request created!")

            return redirect("auth:index")
    else:
        form = SiteRequestForm()

    context = {"form": form}
    return render(request, "request/create.html", context)
