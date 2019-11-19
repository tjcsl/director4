# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Create your views here.


@login_required
def index_view(request):
    return render(request, "sites/list.html")
