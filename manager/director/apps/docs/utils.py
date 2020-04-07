# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import re
import time
import urllib.parse
import xml.etree.ElementTree
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

import bleach
import markdown
import markdown.extensions.toc

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

UTILS_FILE_MTIME = os.path.getmtime(__file__)

# Based off of https://github.com/yourcelf/bleach-whitelist/blob/1b1d5bbced6fa9d5342380c68a57f63720a4d01b/bleach_whitelist/bleach_whitelist.py  # noqa # pylint: disable=line-too-long
ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "b",
    "i",
    "strong",
    "em",
    "tt",
    "p",
    "br",
    "span",
    "div",
    "blockquote",
    "code",
    "hr",
    "ul",
    "ol",
    "li",
    "dd",
    "dt",
    "img",
    "a",
    "sub",
    "sup",
    "small",
    "pre",
]

ALLOWED_ATTRS = {
    "*": ["id"],
    "img": ["src", "alt", "title"],
    "a": ["href", "title"],
}

ALLOWED_STYLES: List[str] = []

cleaner = bleach.sanitizer.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRS,
    styles=ALLOWED_STYLES,
    strip=True,
    strip_comments=True,
)


class LinkRewritingTreeProcessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, md: markdown.Markdown, page: str) -> None:
        super().__init__(md)
        self.page = page.strip("/")

    def run(self, root: xml.etree.ElementTree.Element) -> None:
        self.handle_element(root)

    def handle_element(self, element: xml.etree.ElementTree.Element) -> None:
        # Handle children
        for child in element:
            self.handle_element(child)

        if element.tag == "a":
            href = element.get("href")
            if href is not None:
                element.set("href", rewrite_markdown_link(link_url=href, base_page_name=self.page))


class LinkRewritingExtension(markdown.extensions.Extension):
    def __init__(self, page: str) -> None:
        super().__init__()
        self.page = page

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.treeprocessors.register(LinkRewritingTreeProcessor(md, self.page), "link_rewriter", -100)


def rewrite_markdown_link(*, link_url: str, base_page_name: str) -> str:
    parts = urllib.parse.urlsplit(link_url)

    base_page_name = base_page_name.strip("/")

    # If it's not an external link, rewrite it
    if not parts.netloc and parts.path:
        # Extract the path for rewriting
        path = parts.path

        ext = os.path.splitext(path)[1]
        if not ext or ext == ".md":
            # If there's no file extension, or if it's a link to a markdown file

            if ext == ".md":
                # Remove .md suffixes
                path = path[:-3]

            # Ensure we have exactly one trailing slash
            path = path.rstrip("/") + "/"

        # For other file extensions, do nothing. In particular, no trailing slash.

        if not path.startswith("/"):
            # Make the path absolute by combining with the previous page

            # Remove the last portion and combine with the rest
            if "/" in base_page_name:
                parent_page = base_page_name.rsplit("/", 1)[0]
            else:
                parent_page = ""

            path = os.path.normpath(os.path.join("/", parent_page, path))

        # Recombine and use the new path
        new_parts = (parts.scheme, parts.netloc, path, parts.query, parts.fragment)

        return urllib.parse.urlunsplit(new_parts)
    else:
        return link_url


def url_to_path(url: str) -> Optional[str]:
    # We do some checks that should prevent ".." attacks later, but
    # it's a good idea to check here too
    if ".." in url.split("/"):
        return None

    url = url.rstrip("/")

    director_docs_dir_clean = os.path.normpath(settings.DIRECTOR_DOCS_DIR)
    base_path = os.path.normpath(os.path.join(director_docs_dir_clean, url))

    # Sanity check 1: Make sure they aren't trying to address a file outside the
    # directory.
    if os.path.commonpath([base_path, director_docs_dir_clean]) != director_docs_dir_clean:
        return None

    # Sanity check 2: Don't allow loading hidden files.
    # This implicitly blocks ".." as well.
    for part in url.split("/"):
        if part.startswith("."):
            return None

    return base_path


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

    base_path = url_to_path(page)
    if base_path is None:
        return {}, None

    director_docs_dir_clean = os.path.normpath(settings.DIRECTOR_DOCS_DIR)

    # Render index.md within directories
    potential_paths = [
        (base_path + ".md", ""),
        (os.path.join(base_path, "index.md"), "index"),
    ]

    for path, extra_part in potential_paths:
        # Check if the path exists first
        if not os.path.exists(path):
            continue

        # Treat symlinks as redirects
        if os.path.islink(path):
            redirect_url = rewrite_markdown_link(
                link_url=os.readlink(path), base_page_name=base_page_name,
            )

            return {"Redirect": redirect_url}, ""

        # Resolve symbolic links
        path = os.path.realpath(path)

        # Don't render READMEs
        fname = os.path.basename(path)
        if fname == "README.md":
            continue

        # And check that the path is still within the directory
        if os.path.commonpath([path, director_docs_dir_clean]) != director_docs_dir_clean:
            continue

        cache_name = "docs:" + path

        cached_meta, cached_text_html, cache_creation_time = cache.get(cache_name, ({}, None, 0))
        # If we've cached this file
        if cached_text_html is not None:
            # Get the file modification time
            file_mtime = os.path.getmtime(path)

            # If the cache is newer than both the markdown file AND this file
            if file_mtime < cache_creation_time and UTILS_FILE_MTIME < cache_creation_time:
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
                # We add on the "extra part" because if this was a file like /a/index.md,
                # then links should be interpreted relative to /a.
                # If it was just /a.md, they should be interpreted relative to /.
                LinkRewritingExtension((page + "/" + extra_part).rstrip("/")),
            ],
            tab_length=4,
            output_format="html5",
        )

        text_html = cleaner.clean(markdown_converter.convert(text_md))
        metadata = markdown_converter.Meta  # pylint: disable=no-member

        # Save the data (and the modification time)
        cache.set(
            cache_name,
            (metadata, text_html, time.time()),
            timeout=settings.DIRECTOR_DOCS_CACHE_TIMEOUT,
        )

        return metadata, text_html

    return {}, None


def find_static_file(url: str) -> Optional[str]:
    base_path = url_to_path(url)
    if base_path is None:
        return None

    director_docs_dir_clean = os.path.normpath(settings.DIRECTOR_DOCS_DIR)

    if os.path.commonpath([base_path, director_docs_dir_clean]) != director_docs_dir_clean:
        return None

    return base_path


PAGE_TITLE_REPLACE_RE = re.compile(r"[/-]+")


def get_page_title(page_name: str, metadata: Dict[str, Any]) -> str:
    if "title" in metadata:
        return " ".join(metadata["title"])
    elif page_name:
        return PAGE_TITLE_REPLACE_RE.sub(" ", page_name.strip("/-")).title()
    else:
        return "index"


def iter_page_names() -> Generator[str, None, None]:
    director_docs_dir_clean = os.path.normpath(settings.DIRECTOR_DOCS_DIR)

    seen_files: Set[str] = set()
    seen_dirs: Set[str] = set()

    # Some of the optimizations in here are dependent on the traversal order.
    # Keep topdown=True!
    for root, dirs, files in os.walk(director_docs_dir_clean, topdown=True):
        short_root = os.path.relpath(root, director_docs_dir_clean)
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
