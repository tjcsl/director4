# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Optional

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ...auth.decorators import require_accept_guidelines, superuser_required
from ..forms import DockerImageForm, DockerImageSetupCommandForm
from ..models import DockerImage, DockerImageSetupCommand, Site

# WARNING: Allowing non-superusers to access ANY of the views here presents a major security
# vulnerability!


@superuser_required
@require_accept_guidelines
def home_view(request: HttpRequest) -> HttpResponse:
    context = {
        "images": DockerImage.objects.filter(is_custom=False).order_by("friendly_name"),
        "setup_commands": DockerImageSetupCommand.objects.all(),
    }

    return render(request, "sites/image-mgmt/home.html", context)


@superuser_required
@require_accept_guidelines
def create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DockerImageForm(request.POST)
        if form.is_valid():
            image = form.save(commit=False)
            image.is_custom = False
            image.parent = None
            image.save()

            return redirect("sites:image_mgmt:home")
    else:
        form = DockerImageForm()

    context = {"form": form}

    return render(request, "sites/image-mgmt/edit_create.html", context)


@superuser_required
@require_accept_guidelines
def edit_view(request: HttpRequest, image_id: int) -> HttpResponse:
    image = get_object_or_404(DockerImage, is_custom=False, id=image_id)

    if request.method == "POST":
        form = DockerImageForm(request.POST, instance=image)
        if form.is_valid():
            form.save()
            return redirect("sites:image_mgmt:home")
    else:
        form = DockerImageForm(instance=image)

    context = {"image": image, "form": form}

    return render(request, "sites/image-mgmt/edit_create.html", context)


@superuser_required
@require_accept_guidelines
def delete_view(request: HttpRequest, image_id: int) -> HttpResponse:
    image = get_object_or_404(DockerImage, is_custom=False, id=image_id)

    image_sites = Site.objects.filter(
        Q(docker_image_id=image.id) | Q(docker_image__parent_id=image.id)
    )

    if request.method == "POST" and not image_sites.exists():
        if request.POST["confirm"] == image.name:
            image.delete()

            return redirect("sites:image_mgmt:home")

    context = {"image": image, "image_sites": image_sites}

    return render(request, "sites/image-mgmt/delete.html", context)


@superuser_required
@require_accept_guidelines
def setup_command_edit_create_view(
    request: HttpRequest, command_id: Optional[int] = None
) -> HttpResponse:
    command: Optional[DockerImageSetupCommand]
    if command_id is not None:
        command = get_object_or_404(DockerImageSetupCommand, id=command_id)
    else:
        command = None

    if request.method == "POST":
        form = DockerImageSetupCommandForm(request.POST, instance=command)
        if form.is_valid():
            form.save()
            return redirect("sites:image_mgmt:home")
    else:
        form = DockerImageSetupCommandForm(instance=command)

    context = {"command": command, "form": form}

    return render(request, "sites/image-mgmt/setup_command_edit_create.html", context)


@superuser_required
@require_accept_guidelines
def setup_command_delete_view(request: HttpRequest, command_id: int) -> HttpResponse:
    command = get_object_or_404(DockerImageSetupCommand, id=command_id)

    if request.method == "POST" and not command.docker_images.exists():
        if request.POST["confirm"] == command.name:
            command.delete()

            return redirect("sites:image_mgmt:home")

    context = {"command": command}

    return render(request, "sites/image-mgmt/setup_command_delete.html", context)
