# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import re
import urllib.parse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from ....utils.pagination import paginate
from ...auth.decorators import require_accept_guidelines
from .. import operations
from ..forms import ImageSelectForm, SiteCreateForm
from ..helpers import send_new_site_email
from ..models import DockerImage, Site

SEARCH_QUERY_SPLIT_REGEX = re.compile(r"(^\s*|(?<=\s))(?P<word>(\S|'[^']'|\"[^\"]\")+)(\s*$|\s+)")


@login_required
@require_accept_guidelines
def index_view(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()

    # Split the query string up
    # The re.Scanner class and the associated Pattern.scanner() methods are
    # not documented for some reason, but this is hard to do without them and
    # they should be fairly stable.
    scanner = SEARCH_QUERY_SPLIT_REGEX.scanner(query)  # type: ignore
    query_words = [  # type: ignore
        match.group("word").replace("'", "").replace('"', "")  # type: ignore
        for match in iter(scanner.search, None)
    ]

    # Construct the Site query
    filtered_sites = Site.objects.listable_by_user(request.user)
    for word in query_words:
        # Try to look for fields
        if word.startswith("id:"):
            try:
                val = int(word[3:])
            except ValueError:
                pass
            else:
                filtered_sites = filtered_sites.filter(id=val)
                continue
        elif word.startswith("name:"):
            filtered_sites = filtered_sites.filter(name__icontains=word[5:])
            continue
        elif word.startswith(("desc:", "description:")):
            filtered_sites = filtered_sites.filter(description__icontains=word.split(":", 1)[1])
            continue
        elif word.startswith("user:"):
            filtered_sites = filtered_sites.filter(users__username__iexact=word[5:])
            continue

        # Fall back on just a simple search
        filtered_sites = filtered_sites.filter(
            Q(name__icontains=word)
            | Q(description__icontains=word)
            | Q(users__username__iexact=word)
        )

    # Start with just the sites owned by the user
    own_sites = filtered_sites.filter(users=request.user).annotate(
        user_owns_site=models.Value(True, models.BooleanField())
    )

    # Show results from other sites too if they're a superuser and:
    # - They requested to be shown other sites
    # - OR they entered search terms but nothing matched
    show_all = request.user.is_superuser and bool(
        request.GET.get("all") or (query and not own_sites.exists())
    )

    # Actually add the sites to the query
    if show_all:
        other_sites = filtered_sites.exclude(users=request.user).annotate(
            user_owns_site=models.Value(False, models.BooleanField())
        )

        # This uses an SQL UNION. Django says that most database backends
        # don't support LIMIT or OFFSET in combined queries, but PostgreSQL
        # seems to work fine with it.
        sites = own_sites.union(other_sites)
    else:
        sites = own_sites

    try:
        page_num = int(request.GET["page"])
    except (KeyError, ValueError):
        page_num = 1

    paginated_sites, page_links = paginate(
        # Show sites owned by the user first, then order alphabetically
        sites.order_by("-user_owns_site", "name"),
        page_num=page_num,
        per_page=30,
        prev_text=mark_safe("&laquo;"),
        next_text=mark_safe("&raquo;"),
    )

    context = {
        "show_all": show_all,
        "query": query,
        "page_num": page_num,
        "paginated_sites": paginated_sites,
        "page_links": page_links,
        # Show a banner if the user is graduating soon
        "is_graduating_soon": (
            request.user.graduation_year is not None
            and timezone.localtime().year == request.user.graduation_year
        ),
    }

    return render(request, "sites/list.html", context)


@login_required
@require_accept_guidelines
def terminal_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if request.GET.get("sql") and site.has_database and site.docker_image.is_custom:
        if site.database.db_type == "mysql":
            command = [
                "sh",
                "-c",
                "exec mysql "
                '--host="$DIRECTOR_DATABASE_HOST" '
                '--port="$DIRECTOR_DATABASE_PORT" '
                '--user="$DIRECTOR_DATABASE_USERNAME" '
                '--password="$DIRECTOR_DATABASE_PASSWORD" '
                '"$DIRECTOR_DATABASE_NAME"',
            ]
        else:
            command = ["sh", "-c", 'exec psql "$DIRECTOR_DATABASE_URL"']

        command_str = urllib.parse.quote_plus("\n".join(command))
    else:
        command_str = ""

    context = {
        "site": site,
        "command_str": command_str,
    }

    return render(request, "sites/terminal.html", context)


@login_required
@require_accept_guidelines
def regen_nginx_config_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    if request.method == "POST":
        operations.regen_nginx_config(site)

    return redirect("sites:info", site.id)


@login_required
@require_accept_guidelines
def create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SiteCreateForm(request.POST, user=request.user)
        if form.is_valid():
            site = form.save(commit=False)

            site.docker_image = DockerImage.objects.get_default_image()  # type: ignore
            site.save()
            form.save_m2m()

            operations.create_site(site)

            for user in site.users.filter(is_service=False).exclude(id=request.user.id):
                send_new_site_email(user=user, site=site)

            return redirect("sites:info", site.id)
    else:
        form = SiteCreateForm(user=request.user)

    context = {"form": form}

    return render(request, "sites/create.html", context)


@login_required
@require_accept_guidelines
def create_webdocs_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_superuser:
        return redirect("sites:create")

    webdocs_site = Site.objects.listable_by_user(request.user).filter(purpose="user").first()
    if webdocs_site is not None:
        return redirect("sites:info", webdocs_site.id)

    if request.method == "POST":
        form = SiteCreateForm(request.POST, user=request.user, initial={"purpose": "user"})
        if form.is_valid():
            site = form.save(commit=False)

            site.docker_image = DockerImage.objects.get_default_image()  # type: ignore
            site.save()
            form.save_m2m()

            operations.create_site(site)

            return redirect("sites:info", site.id)
    else:
        form = SiteCreateForm(user=request.user, initial={"purpose": "user"})

    context = {"form": form}

    return render(request, "sites/create.html", context)


@login_required
@require_accept_guidelines
def info_view(request: HttpRequest, site_id: int) -> HttpResponse:
    # WARNING: Because we use listable_by_user() instead of editable_by_user() here,
    # we have to check site.can_be_edited_by() manually and handle that accordingly.

    site = get_object_or_404(Site.objects.listable_by_user(request.user), id=site_id)

    context = {"site": site, "can_edit": site.can_be_edited_by(request.user)}
    return render(request, "sites/info.html", context)


@login_required
@require_accept_guidelines
def image_select_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    # This logic blocks the user from trying to change the image if an operation is running.
    # However, if the operation has failed and the cause of the failure was an error while
    # building the Docker image, we make a special exception and allow the user to change
    # the image.
    override_failed_operation = False
    operation = site.get_operation()

    if operation is not None:
        if (
            # The operation failed
            operation.has_failed
            # The failure is recoverable by the user
            and operation.is_failure_user_recoverable
            # The operation has no failed recoverable actions that do not have the
            # `build_docker_image` slug.
            # i.e. the Action that failed was `build_docker_image`.
            and not operation.action_set.filter(result=False, user_recoverable=False)
            .exclude(slug="build_docker_image")
            .exists()
        ):
            override_failed_operation = True
        else:
            messages.error(request, "An operation is already being performed on this site")
            return redirect("sites:info", site.id)

    if request.method == "POST":
        form = ImageSelectForm(request.POST)
        if form.is_valid():
            if override_failed_operation and operation is not None:
                operation.action_set.all().delete()
                operation.delete()

            operations.update_image(
                site,
                form.cleaned_data["image"],
                form.cleaned_data["write_run_sh_file"],
                form.cleaned_data["packages"].strip().split(),
            )

            return redirect("sites:info", site.id)
    else:
        form = ImageSelectForm(
            initial={
                "image": site.docker_image.parent,
                "write_run_sh_file": False,
                "packages": " ".join(
                    site.docker_image.extra_packages.values_list("name", flat=True)
                ),
            }
        )

    image_subwidgets_and_objs = []
    for subwidget in form["image"].subwidgets:  # type: ignore
        try:
            image = DockerImage.objects.filter_user_visible().get(  # type: ignore
                name=subwidget.data["value"]
            )
        except DockerImage.DoesNotExist:
            image = None

        image_subwidgets_and_objs.append((subwidget, image))

    context = {
        "override_failed_operation": override_failed_operation,
        "site": site,
        "form": form,
        "image_subwidgets_and_objs": image_subwidgets_and_objs,
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
@require_accept_guidelines
def regenerate_secrets_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    operations.regen_site_secrets(site)

    return redirect("sites:info", site.id)


@require_POST
@login_required
@require_accept_guidelines
def restart_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    operations.restart_service(site)

    return redirect("sites:info", site.id)


@require_POST
@login_required
@require_accept_guidelines
def restart_raw_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if site.has_operation:
        return HttpResponse("An operation is already being performed on this site", status=500)

    operations.restart_service(site)

    return HttpResponse("")


@login_required
@require_accept_guidelines
def delete_view(request: HttpRequest, site_id: int) -> HttpResponse:
    site = get_object_or_404(Site.objects.editable_by_user(request.user), id=site_id)

    if site.has_operation:
        messages.error(request, "An operation is already being performed on this site")
        return redirect("sites:info", site.id)

    if request.method == "POST":
        if request.POST.get("confirm") == site.name:
            operations.delete_site(site)
            return redirect("sites:info", site.id)

    return render(request, "sites/delete.html", {"site": site})
