# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .. import operations
from ..forms import ImageSelectForm, SiteCreateForm
from ..models import DockerImage, Site


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
def terminal_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    context = {
        "site": site,
    }

    return render(request, "sites/terminal.html", context)


@login_required
def regen_nginx_config_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    if request.method == "POST":
        operations.regen_nginx_config(site)

    return redirect("sites:info", site.id)


@login_required
def create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SiteCreateForm(request.POST)
        if form.is_valid():
            site = form.save(commit=False)

            site.docker_image = DockerImage.objects.get_default_image()  # type: ignore
            site.save()
            form.save_m2m()

            operations.create_site(site)

            return redirect("sites:info", site.id)
    else:
        form = SiteCreateForm()

    context = {"form": form}

    return render(request, "sites/create.html", context)


@login_required
def info_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    context = {"site": site}
    return render(request, "sites/info.html", context)


@login_required
def image_select_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        form = ImageSelectForm(request.POST)
        if form.is_valid():
            # pylint: disable=unused-variable
            docker_image = DockerImage.objects.filter_user_visible().get(  # type: ignore  # noqa
                name=form.cleaned_data["image"]
            )
            write_run_sh_file = form.cleaned_data["write_run_sh_file"]  # noqa
    else:
        form = ImageSelectForm(initial={"image": site.docker_image, "write_run_sh_file": False})

    image_subwidgets_and_data = []
    for subwidget in form["image"].subwidgets:  # type: ignore
        try:
            image = DockerImage.objects.filter_user_visible().get(  # type: ignore
                name=subwidget.data["value"]
            )
        except DockerImage.DoesNotExist:
            image_data = {}
        else:
            image_data = {"has_run_sh_template": bool(image.run_script_template)}

        image_subwidgets_and_data.append((subwidget, image_data))

    context = {
        "site": site,
        "form": form,
        "image_subwidgets_and_data": image_subwidgets_and_data,
        "image_json": json.dumps(
            {
                image.name: {
                    "friendly_name": image.friendly_name,
                    "run_script_template": image.run_script_template,
                }
                for image in DockerImage.objects.filter_user_visible()  # type: ignore
            }
        ),
    }
    return render(request, "sites/image_select.html", context)


@require_POST
@login_required
def regenerate_secrets_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    operations.regen_site_secrets(site)

    return redirect("sites:info", site.id)


@require_POST
@login_required
def restart_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    operations.restart_service(site)

    return redirect("sites:info", site.id)
