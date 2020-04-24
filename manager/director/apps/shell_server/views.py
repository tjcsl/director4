# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import time

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..sites.models import Site
from .helpers import authenticate_kinit, generate_token


@csrf_exempt
@require_POST
def authenticate_view(request: HttpRequest) -> HttpResponse:
    if any(key not in request.POST for key in ["username", "password"]):
        return HttpResponse(status=400)

    username = request.POST["username"]

    user = authenticate_kinit(username, request.POST["password"])

    if user is None:
        return HttpResponse(status=401)

    sites = {}
    # filter_for_user() returns all sites for superusers, which can be a little... overwhelming.
    for site in Site.objects.filter(users=user):
        token = generate_token(site, expire_time=time.time() + 60)

        sites[site.name] = [site.id, token.decode("latin-1")]

    return JsonResponse(sites, status=200)
