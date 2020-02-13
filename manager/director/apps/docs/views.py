# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from .utils import load_doc_page


@login_required
def doc_page_view(request: HttpRequest, page_name: str = "") -> HttpResponse:
    metadata, text_html = load_doc_page(page_name)

    if text_html is None:
        raise Http404

    context = {
        "doc_content": text_html,
        "title": metadata.get("title", page_name.rstrip("/").split("/")[-1]),
    }

    return render(request, "docs/doc_page.html", context)
