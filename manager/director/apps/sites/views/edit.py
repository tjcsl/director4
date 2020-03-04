# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .. import operations
from ..forms import DomainFormSet, SiteMetaForm, SiteNamesForm, SiteTypeForm
from ..helpers import send_site_updated_message
from ..models import Domain, Site


@login_required
def edit_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    context = {
        "site": site,
        "names_form": SiteNamesForm.build_for_site(site),
        "domains_formset": DomainFormSet(
            initial=site.domain_set.values("domain"), prefix="domains"
        ),
        "meta_form": SiteMetaForm(instance=site, user=request.user),
        "type_form": SiteTypeForm({"type": site.type}),
    }

    return render(request, "sites/edit.html", context)


@login_required
def edit_meta_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        meta_form = SiteMetaForm(request.POST, instance=site, user=request.user)
        if meta_form.is_valid():
            meta_form.save()
            send_site_updated_message(site)
            return redirect("sites:info", site.id)
    else:
        meta_form = SiteMetaForm(instance=site, user=request.user)

    context = {"site": site, "meta_form": meta_form}

    return render(request, "sites/edit.html", context)


@login_required
def edit_names_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        names_form = SiteNamesForm(request.POST)
        domains_formset = DomainFormSet(
            request.POST,
            prefix="domains",
            form_kwargs={"user_is_superuser": request.user.is_superuser},
        )
        if site.has_operation:
            messages.error(request, "An operation is already being performed on this site")
        elif names_form.is_valid() and domains_formset.is_valid():
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
            elif (
                Site.objects.filter(name=names_form.cleaned_data["name"])
                .exclude(id=site.id)
                .exists()
            ):
                messages.error(request, "There is another site with the name you have requested")
            else:
                operations.edit_site_names(
                    site,
                    new_name=names_form.cleaned_data["name"],
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
def edit_type_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.filter_for_user(request.user), id=site_id)

    if request.method == "POST":
        type_form = SiteTypeForm(request.POST)
        if type_form.is_valid():
            operations.change_site_type(site, type_form.cleaned_data["type"])

            return redirect("sites:info", site.id)
    else:
        type_form = SiteTypeForm({"type": site.type})

    context = {"site": site, "type_form": type_form}

    return render(request, "sites/edit.html", context)
