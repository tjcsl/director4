# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ...utils.appserver import AppserverRequestError, appserver_open_http_request
from . import operations
from .forms import DatabaseCreateForm, DomainFormSet, SiteCreateForm, SiteMetaForm, SiteNamesForm
from .models import Action, DockerImage, Domain, Operation, Site


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


def prometheus_metrics_view(request: HttpRequest) -> HttpResponse:
    remote_addr = (
        request.META["HTTP_X_REAL_IP"]
        if "HTTP_X_REAL_IP" in request.META
        else request.META.get("REMOTE_ADDR", "")
    )

    if (
        request.user.is_authenticated and request.user.is_superuser
    ) or remote_addr in settings.ALLOWED_METRIC_SCRAPE_IPS:
        metrics = {"director4_sites_failed_actions": Action.objects.filter(result=False).count()}

        return render(
            request, "prometheus-metrics.txt", {"metrics": metrics}, content_type="text/plain"
        )
    else:
        raise Http404


def operations_view(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise Http404

    if request.GET.get("failed"):
        title = "Failed Operations"
        failed_only = True
        operation_objs = Operation.objects.filter(action__result=False).distinct()
    else:
        title = "Operations"
        failed_only = False
        operation_objs = Operation.objects.all()

    context = {
        "title": title,
        "failed_only": failed_only,
        "operations": operation_objs,
    }

    return render(request, "sites/operations.html", context)


# Used for routes that do not have views written but need to be linked to
@login_required
def dummy_view(  # pylint: disable=unused-argument
    request: HttpRequest, site_id: Optional[int] = None
) -> HttpResponse:
    return HttpResponse("")


@login_required
def edit_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    context = {
        "site": site,
        "names_form": SiteNamesForm.build_for_site(site),
        "domains_formset": DomainFormSet(
            initial=site.domain_set.values("domain"), prefix="domains"
        ),
        "meta_form": SiteMetaForm(instance=site),
    }

    return render(request, "sites/edit.html", context)


@login_required
def edit_meta_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        meta_form = SiteMetaForm(request.POST, instance=site)
        if meta_form.is_valid():
            meta_form.save()
            return redirect("sites:info", site.id)
    else:
        meta_form = SiteMetaForm(instance=site)

    context = {"site": site, "meta_form": meta_form}

    return render(request, "sites/edit.html", context)


@login_required
def edit_names_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        names_form = SiteNamesForm(request.POST)
        domains_formset = DomainFormSet(request.POST, prefix="domains")
        if names_form.is_valid() and domains_formset.is_valid():
            domains = [
                form.cleaned_data["domain"]
                for form in domains_formset.forms
                if form.cleaned_data.get("domain")
            ]
            if Domain.objects.filter(domain__in=domains).exclude(site__id=site.id).exists():
                messages.error(
                    request,
                    "The following domain(s) you requested are already in use: {}".format(
                        ", ".join(
                            Domain.objects.filter(domain__in=domains)
                            .exclude(site__id=site.id)
                            .values_list("domain", flat=True)
                        )
                    ),
                )
            else:
                operations.edit_site_names(
                    site,
                    new_name=names_form.cleaned_data["name"],
                    sites_domain_enabled=names_form.cleaned_data["sites_domain_enabled"],
                    domains=domains,
                    request_username=request.user.username,
                )
                return redirect("sites:info", site.id)
    else:
        names_form = SiteNamesForm.build_for_site(site)
        domains_formset = DomainFormSet(initial=site.domain_set.values("domain"), prefix="domains")

    context = {"site": site, "names_form": names_form, "domains_formset": domains_formset}

    return render(request, "sites/edit.html", context)


@login_required
def regen_nginx_config_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        operations.regen_nginx_config(site)

    return redirect("sites:info", site.id)


@login_required
def create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SiteCreateForm(request.POST)
        if form.is_valid():
            site = form.save(commit=False)

            docker_image = DockerImage.objects.create(name="tmp_site_" + site.name, is_custom=True)
            site.docker_image = docker_image
            site.save()
            form.save_m2m()
            docker_image.name = "site_{}".format(site.id)

            operations.create_site(site)

            return redirect("sites:info", site.id)
    else:
        form = SiteCreateForm()

    context = {"form": form}

    return render(request, "sites/create.html", context)


@require_POST
@login_required
def demo_view(request: HttpRequest) -> HttpResponse:
    try:
        # Connect to a random appserver
        resp = appserver_open_http_request(-1, "/demo", method="POST")
    except AppserverRequestError as ex:
        messages.error(request, "Error connecting to appserver: {}".format(ex))
    except json.JSONDecodeError as ex:
        messages.error(request, "Invalid response from appserver: {}".format(ex))
    else:
        messages.info(
            request, "Response from appserver #{}: {}".format(resp.appserver_index + 1, resp.text)
        )

    return redirect("auth:index")


@login_required
def info_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    context = {"site": site}
    return render(request, "sites/info.html", context)


@login_required
def create_database_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if site.database is not None:
        return redirect("sites:info", site.id)

    if request.method == "POST":
        form = DatabaseCreateForm(request.POST)
        if form.is_valid():
            operations.create_database(site, form.cleaned_data["host"])
            return redirect("sites:info", site.id)
    else:
        form = DatabaseCreateForm()

    context = {"site": site, "form": form}

    return render(request, "sites/databases/create.html", context)


@login_required
def delete_database_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        if request.POST.get("confirm") == site.name:
            operations.delete_database(site)
            return redirect("sites:info", site.id)

    return render(request, "sites/databases/delete.html", {"site": site})


@require_POST
@login_required
def regenerate_secrets_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    operations.regen_site_secrets(site)

    return redirect("sites:info", site.id)
