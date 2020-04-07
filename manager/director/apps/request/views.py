# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ...utils.emails import send_email
from .forms import SiteRequestForm
from .models import SiteRequest


@login_required
def approve_teacher_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_teacher:
        messages.error(request, "You are not authorized to approve requests.")
        return redirect("auth:index")

    if request.method == "POST":
        try:
            site_request = SiteRequest.objects.get(
                id=request.POST.get("request", None), teacher=request.user
            )
        except SiteRequest.DoesNotExist:
            messages.error(
                request,
                "Either that site request does not exist or you do not have permission to approve "
                "it.",
            )
        else:
            action = request.POST.get("action", None)
            if action == "accept":
                if not request.POST.get("agreement", False):
                    messages.error(
                        request, "Please check the agreement box to approve this site request!"
                    )
                else:
                    site_request.teacher_approval = True
                    site_request.save()

                    send_email(
                        text_template="emails/admin_approve_request.txt",
                        html_template="emails/admin_approve_request.html",
                        context={"site_request": site_request, "DJANGO_SETTINGS": settings},
                        subject="A website request has been approved",
                        emails=[settings.DIRECTOR_CONTACT_EMAIL],
                        bcc=False,
                    )

                    messages.success(
                        request,
                        "Your approval has been added and the site will be created shortly.",
                    )
            elif action == "reject":
                site_request.teacher_approval = False
                site_request.save()
                messages.success(request, "You have rejected this site request.")

        return redirect("request:approve_teacher")

    context = {
        "site_requests": SiteRequest.objects.filter(teacher=request.user).order_by(
            "-teacher_approval", "-id"
        ),
    }

    return render(request, "request/approve-teacher.html", context)


@login_required
def approve_admin_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_superuser:
        messages.error(request, "Only administrators can perform the final approval.")
        return redirect("auth:index")

    if request.method == "POST":
        try:
            site_request = SiteRequest.objects.get(
                id=request.POST.get("request", None), teacher_approval=True
            )
        except SiteRequest.DoesNotExist:
            messages.error(
                request,
                "Either that site request does not exist or it has not been approved by a teacher.",
            )
        else:
            admin_comments = request.POST.get("admin_comments", "")
            private_admin_comments = request.POST.get("private_admin_comments", "")

            site_request.admin_comments = admin_comments
            site_request.private_admin_comments = private_admin_comments
            site_request.save()

            action = request.POST.get("action", None)
            if action == "accept":
                site_request.admin_approval = True
                site_request.save()
                messages.success(request, "Request marked as processed.")
            elif action == "reject":
                site_request.admin_approval = False
                site_request.save()
                messages.success(request, "Request marked as rejected.")

        return redirect("request:approve_admin")

    context = {
        "site_requests": SiteRequest.objects.order_by("-id"),
    }

    return render(request, "request/approve-admin.html", context)


@login_required
def status_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_student:
        messages.error(request, "Only students can view this page.")
        return redirect("auth:index")

    context = {
        "site_requests": SiteRequest.objects.filter(user=request.user).order_by("-id"),
    }

    return render(request, "request/status.html", context)


@login_required
def create_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_student:
        messages.error(request, "Only students can view this page.")
        return redirect("auth:index")

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
                bcc=False,
            )

            messages.success(request, "Website request created!")

            return redirect("auth:index")
    else:
        form = SiteRequestForm()

    context = {"form": form}
    return render(request, "request/create.html", context)
