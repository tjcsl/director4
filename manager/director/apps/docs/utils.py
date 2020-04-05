# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
import time
import urllib.parse
import xml.etree.ElementTree
from typing import Any, Dict, Generator, Optional, Set, Tuple

import markdown
import markdown.extensions.toc

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse


class LinkRewritingTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def run(self, root: xml.etree.ElementTree.Element) -> None:
        self.handle_element(root)

    def handle_element(self, element: xml.etree.ElementTree.Element) -> None:
        # Handle children
        for child in element:
            self.handle_element(child)

        if element.tag == "a":
            href = element.get("href")
            if href is not None:
                parts = urllib.parse.urlsplit(href)

                # If it's not an external link, rewrite it
                if not parts.netloc:
                    # Extract the path for rewriting
                    path = parts.path

                    # Strip trailing slashes
                    path = path.rstrip("/")

                    # Remove .md suffixes
                    if path.endswith(".md"):
                        path = path[:-3]

                    # Rewrite "/"-prefixed URLs to make them relative to the main docs app
                    if path.startswith("/"):
                        path = reverse("docs:doc_page", args=[path.lstrip("/")])

                    # Recombine and use the new path
                    new_parts = (parts.scheme, parts.netloc, path, parts.query, parts.fragment)

                    # Update the element
                    element.set("href", urllib.parse.urlunsplit(new_parts))


class LinkRewritingExtension(markdown.extensions.Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(LinkRewritingTreeProcessor(md), "link_rewriter", -100)


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
    ]

    for path in potential_paths:
        # Check if the path exists first
        if not os.path.exists(path):
            continue

        # Resolve symbolic links
        path = os.path.realpath(path)

        # Don't render READMEs
        fname = os.path.basename(path)
        if fname == "README.md":
            continue

        # And check that the path is still within the directory
        if os.path.commonpath([path, director_dir_clean]) != director_dir_clean:
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
            text_md = f_obj.read()

        # Render as HTML
        markdown_converter = markdown.Markdown(
            extensions=[
                "fenced_code",
                "footnotes",
                "tables",
                "meta",
                "nl2br",
                markdown.extensions.toc.TocExtension(
                    permalink="", permalink_class="headerlink fa fa-link",
                ),
                LinkRewritingExtension(),
            ],
        )

        text_html = markdown_converter.convert(text_md)
        metadata = markdown_converter.Meta  # pylint: disable=no-member

        # Save the data (and the modification time)
        cache.set(
            cache_name,
            (metadata, text_html, time.time()),
            timeout=settings.DIRECTOR_DOCS_CACHE_TIMEOUT,
        )

        return metadata, text_html

    return {}, None


PAGE_TITLE_REPLACE_RE = re.compile(r"[/-]+")


def get_page_title(page_name: str, metadata: Dict[str, Any]) -> str:
    if "title" in metadata:
        return " ".join(metadata["title"])
    elif page_name:
        return PAGE_TITLE_REPLACE_RE.sub(" ", page_name.strip("/-")).title()
    else:
        return "index"


def iter_page_names() -> Generator[str, None, None]:
    director_dir_clean = os.path.normpath(settings.DIRECTOR_DOCS_DIR)

    seen_files: Set[str] = set()
    seen_dirs: Set[str] = set()

    # Some of the optimizations in here are dependent on the traversal order.
    # Keep topdown=True!
    for root, dirs, files in os.walk(director_dir_clean, topdown=True):
        short_root = os.path.relpath(root, director_dir_clean)
        if short_root == ".":
            short_root = ""

        seen_files.update(os.path.join(root, fname) for fname in files)
        seen_dirs.update(os.path.join(root, dname) for dname in dirs)

        for fname in files:
            if not fname.endswith(".md"):
                continue

            if fname == "README.md":
                continue

            page_name = os.path.join(short_root, fname[:-3])

            if fname == "index.md":
                # Example path so far: a/index.md

                # The "not in seen_files" trick here reduces the number of stat() calls,
                # but it only works because we only check files in the current directory
                # or parent directories (which we've seen because we're going top down).
                if root.rstrip("/") + ".md" not in seen_files:
                    # a.md does not exist. So if they go to /a, they will get this page
                    # (a/index.md).
                    page_name = short_root.rstrip("/")

            yield page_name
