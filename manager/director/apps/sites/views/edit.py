# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ...auth.decorators import require_accept_guidelines
from .. import operations
from ..forms import DomainFormSet, SiteMetaForm, SiteNamesForm, SiteTypeForm
from ..helpers import send_new_site_email, send_site_updated_message
from ..models import Domain, Site


@login_required
@require_accept_guidelines
def edit_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    context = {
        "site": site,
        "names_form": SiteNamesForm(site=site),
        "domains_formset": DomainFormSet(
            initial=site.domain_set.values("domain"), prefix="domains"
        ),
        "meta_form": SiteMetaForm(instance=site, user=request.user),
        "type_form": SiteTypeForm({"type": site.type}),
    }

    return render(request, "sites/edit.html", context)


@login_required
@require_accept_guidelines
def edit_meta_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if request.method == "POST":
        meta_form = SiteMetaForm(request.POST, instance=site, user=request.user)
        if meta_form.is_valid():
            # Get the list so we can see who was added later
            old_uids = list(site.users.values_list("id", flat=True))

            meta_form.save()
            send_site_updated_message(site)

            for user in site.users.filter(is_service=False).exclude(
                id__in=[request.user.id, *old_uids]
            ):
                send_new_site_email(user=user, site=site)

            return redirect("sites:info", site.id)
    else:
        meta_form = SiteMetaForm(instance=site, user=request.user)

    context = {"site": site, "meta_form": meta_form}

    return render(request, "sites/edit.html", context)


@login_required
@require_accept_guidelines
def edit_names_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    # See image_select_view() in views/sites.py
    override_failed_operation = False
    operation = site.get_operation()

    if operation is not None:
        if (
            # The operation failed
            operation.has_failed
            # The failure is recoverable by the user
            and operation.is_failure_user_recoverable
            # The operation has no failed recoverable actions that do not have the
            # `update_balancer_certbot` slug.
            # i.e. the Action that failed was `update_balancer_certbot`.
            and not operation.action_set.filter(result=False, user_recoverable=False)
            .exclude(slug="update_balancer_certbot")
            .exists()
        ):
            override_failed_operation = True
        else:
            messages.error(request, "An operation is already being performed on this site")
            return redirect("sites:info", site.id)

    if request.method == "POST":
        names_form = SiteNamesForm(request.POST, site=site)
        domains_formset = DomainFormSet(
            request.POST,
            prefix="domains",
            form_kwargs={"user_is_superuser": request.user.is_superuser},
        )

        if names_form.is_valid() and domains_formset.is_valid():
            domains = [
                form.cleaned_data["domain"]
                for form in domains_formset.forms
                if form.cleaned_data.get("domain")
            ]

            if (
                Domain.objects.filter(domain__in=domains)
                .exclude(site__id=site.id)
                .exclude(status="deleted")
                .exists()
            ):
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
                if override_failed_operation and operation is not None:
                    operation.action_set.all().delete()
                    operation.delete()

                operations.edit_site_names(
                    site,
                    new_name=names_form.cleaned_data["name"],
                    domains=domains,
                    request_username=request.user.username,
                )
                return redirect("sites:info", site.id)
    else:
        names_form = SiteNamesForm(site=site)
        domains_formset = DomainFormSet(initial=site.domain_set.values("domain"), prefix="domains")

    context = {"site": site, "names_form": names_form, "domains_formset": domains_formset}

    return render(request, "sites/edit.html", context)


@login_required
@require_accept_guidelines
def edit_type_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if request.method == "POST":
        type_form = SiteTypeForm(request.POST)
        if type_form.is_valid():
            operations.change_site_type(site, type_form.cleaned_data["type"])

            return redirect("sites:info", site.id)
    else:
        type_form = SiteTypeForm({"type": site.type})

    context = {"site": site, "type_form": type_form}

    return render(request, "sites/edit.html", context)
