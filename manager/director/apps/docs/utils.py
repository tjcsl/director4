# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import markdown
import markdown.extensions.toc

from django.conf import settings
from django.core.cache import cache


def load_doc_page(page: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """Given the name of a documentation page, this function finds the correct file within
    ``settings.DIRECTOR_DOCS_DIR``, extracts JSON-encoded metadata from a
    "<!-- META: ... -->" comment on the first line if it is present, and returns 1) the metadata
    and 2) the HTML to render (or None of the page is not found).

    This function caches the rendered HTML. It does, however, check the file modification dates
    to see if detecting if the cache is out-of-date, and it ignores the cache if this is the
    case. This avoids the need to clear the cache whenever the original Markdown files are
    updated.

    This function blocks the following potential security breaches:
    1. Attempts to access files outside the repo (for example, through use of "..")
    2. Attempts to access hidden files (the docs are in a Git repository, so we need
       to block access to ".git", and while we're at it let's block all hidden files)

    Args:
        page: The name of the documentation page to retrieve.

    Returns:
        A tuple of (metadata, text_html) where text_html is the HTML to render or None if
        the page was not found.

    """

    # We do some checks that should prevent ".." attacks later, but
    # it's a good idea to check here too
    if ".." in page.split("/"):
        return {}, None

    page = page.rstrip("/")

    director_dir_clean = os.path.normpath(settings.DIRECTOR_DOCS_DIR)
    base_path = os.path.normpath(os.path.join(director_dir_clean, page))

    # Sanity check 1: Make sure they aren't trying to address a file outside the
    # directory.
    if os.path.commonpath([base_path, director_dir_clean]) != director_dir_clean:
        return {}, None

    # Sanity check 2: Don't allow loading hidden files.
    # This implicitly blocks ".." as well.
    for part in page.split("/"):
        if part.startswith("."):
            return {}, None

    # Render index.md within directories
    potential_paths = [
        base_path + ".md",
        os.path.join(base_path, "index.md"),
        os.path.join(base_path, "README.md"),
    ]

    for path in potential_paths:
        # Check if the path exists first
        if not os.path.exists(path):
            continue

        cache_name = "docs:" + path

        cached_meta, cached_text_html, cache_creation_time = cache.get(cache_name, ({}, None, 0))
        # If we've cached this file
        if cached_text_html is not None:
            # Get the file modification time
            file_mtime = os.path.getmtime(path)

            # If the cache is newer than the file
            if file_mtime < cache_creation_time:
                return cached_meta, cached_text_html

        with open(path) as f_obj:
            # We use readlines() instead of read() because it's easier to work with
            # a list of lines when we do some editing later
            lines = f_obj.readlines()

        # Extract embedded "metadata"
        metadata = {}
        meta_prefix = "<!-- META: "
        meta_suffix = " -->"
        if lines:
            first_line = lines[0].strip()
            if first_line.startswith(meta_prefix) and first_line.strip().endswith(meta_suffix):
                lines.pop(0)
                metadata = json.loads(first_line[len(meta_prefix): -len(meta_suffix)].strip())

        # Reconstruct the original text
        text_md = "".join(lines)

        # Render as HTML
        text_html = markdown.markdown(
            text_md,
            extensions=[
                "fenced_code",
                "footnotes",
                "tables",
                markdown.extensions.toc.TocExtension(
                    permalink="", permalink_class="headerlink fa fa-link",
                ),
            ],
        )

        # Save the data (and the modification time)
        cache.set(
            cache_name,
            (metadata, text_html, time.time()),
            timeout=settings.DIRECTOR_DOCS_CACHE_TIMEOUT,
        )

        return metadata, text_html

    return {}, None
