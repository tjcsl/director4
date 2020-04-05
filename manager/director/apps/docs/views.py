# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import re
from typing import Any, Dict, List, Tuple

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .utils import get_page_title, iter_page_names, load_doc_page


@require_GET
@login_required
def doc_page_view(request: HttpRequest, page_name: str = "") -> HttpResponse:
    if "//" in page_name or page_name.startswith("/") or page_name.endswith("/"):
        return redirect("docs:doc_page", re.sub(r"/+", "/", page_name.strip("/")))

    metadata, text_html = load_doc_page(page_name)

    if text_html is None:
        raise Http404

    context = {
        "doc_page": page_name,
        "doc_content": text_html,
        "title": get_page_title(page_name, metadata),
    }

    return render(request, "docs/doc_page.html", context)


@login_required
def search_view(request: HttpRequest) -> HttpResponse:
    context: Dict[str, Any] = {}

    query = request.GET.get("q", request.POST.get("q", ""))
    if query:
        query_words = list(map(str.lower, query.split()))

        results: List[Tuple[str, str, int]] = []

        for page_name in iter_page_names():
            metadata, text_html = load_doc_page(page_name)
            if text_html is None:
                continue

            title = get_page_title(page_name, metadata)

            rank = sum(
                title.lower().count(word) * 2 + text_html.lower().count(word)
                for word in query_words
            )

            if rank > 0:
                results.append((page_name, title, rank))

        context["results"] = sorted(results, key=lambda result: result[-1], reverse=True)

    context["query"] = query

    return render(request, "docs/search.html", context)
