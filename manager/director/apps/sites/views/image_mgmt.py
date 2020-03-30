# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ...auth.decorators import superuser_required
from ..forms import DockerImageForm
from ..models import DockerImage, Site

# WARNING: Allowing non-superusers to access ANY of the views here presents a major security
# vulnerability!


@superuser_required
def home_view(request: HttpRequest) -> HttpResponse:
    context = {"images": DockerImage.objects.filter(is_custom=False)}

    return render(request, "sites/image-mgmt/home.html", context)


@superuser_required
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
