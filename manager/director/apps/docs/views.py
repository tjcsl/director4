# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
from typing import Any, Dict, List, Tuple, Union

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .utils import find_static_file, get_page_title, iter_page_names, load_doc_page

# *** WARNING WARNING WARNING: Read this carefully before making any URL routing changes ***
# Here's how routing works.
# Let's say we have the following setup:
# - a.py
# - b.md
# - c.d/
#   - index.md
# Requests to /a.py will return the contents of a.py because there's an extension in
#   the last portion of the URL, and that triggers a check for static files.
# Requests to /a.py/ will 404 because the slash "hides" the extension. THIS IS VERY
#   IMPORTANT.
# Requests to /b will 302 to /b/.
# Requests to /b/ will render b.md and return the result.
# Requests to /c.d will 302 to /c.d/, but only once we have:
#   1. Checked for a *file* named "c.d" and found nothing.
#   2. Checked for a page named "c.d" and confirmed that it exists.
# Requests to /c/ will render c/index.md and return the result.
# Requests to /NOEXIST will 302 to /NOEXIST/ because there is no extension to trigger
#   a static file check
# Requests to /NOEXIST/ will 404 because NOEXIST.md does not exist and NOEXIST/index.md
#   does not exist.
# Requests to /NOEXIST.py will 404. They will NOT 302 to /NOEXIST.py/. If we did that,
#   then if we later added a static file with that name, things might break (in
#   certain weird circumstances).


@require_GET
@login_required
def doc_page_view(request: HttpRequest, url: str = "") -> Union[FileResponse, HttpResponse]:
    ext = os.path.splitext(url)[1]  # This will be empty if the path ends with a "/"

    if ext == ".md":
        return redirect("docs:doc_page", url[:-3] + "/")
    elif ext:
        fpath = find_static_file(url)
        if fpath is not None and os.path.isfile(fpath):
            try:
                f_obj = open(fpath, "rb")
            except FileNotFoundError:
                pass
            else:
                return FileResponse(f_obj)

        # We didn't find a static file that matches. Fall through.

    # Sanitize URLs slightly
    if "//" in url or url.startswith("/"):
        return redirect("docs:doc_page", re.sub(r"/+", "/", url.strip("/") + "/"))

    # So far, only redirect if there was no extension.
    # If there was an extension, then that indicates a static file
    if not ext and url and not url.endswith("/"):
        return redirect("docs:doc_page", url + "/")

    metadata, text_html = load_doc_page(url)

    if text_html is None:
        raise Http404

    if metadata.get("Redirect"):
        return redirect("docs:doc_page", metadata.get("Redirect").lstrip("/"))

    # We know that the page exists. Now make sure the URL ends with a "/".
    if url and not url.endswith("/"):
        return redirect("docs:doc_page", url + "/")

    context = {
        "doc_page": url.strip("/"),
        "doc_content": text_html,
        "title": get_page_title(url, metadata),
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
