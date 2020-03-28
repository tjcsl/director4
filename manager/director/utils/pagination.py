# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, List, Optional, Sequence, Tuple, Union

from django.core.paginator import Paginator
from django.utils.safestring import SafeString


def paginate(
    items: Any,
    page_num: int,
    *,
    per_page: int = 10,
    num_start: int = 2,
    num_end: int = 2,
    num_around: int = 1,
    current_link: bool = False,
    prev_text: Union[str, SafeString] = "<",
    next_text: Union[str, SafeString] = ">",
    spacer_text: Union[str, SafeString] = "...",
    always_show_prev_text: bool = True,
    always_show_next_text: bool = True,
) -> Tuple[Sequence, List[Tuple[str, Optional[int]]]]:
    """Paginates a set of items.

    Args:
        items: The items to paginate.
        page_num: The current page number, starting at 1.
        per_page: The number of items to display per page.
        num_start: If non-zero, links will always be shown to the first <num_start> pages,
            regardless of how far the current page is away from them.
        num_end: If non-zero, links will always be shown to the last <num_end> pages,
            regardless of how far the current page is away from them.
        num_around: If non-zero, links will always be shown to the given number of pages on either
            side of the current page (assuming those pages exist).
        current_link: If true, then the current page will be included as a link. By default, it is
            given a None page (see Returns).
        prev_text: The text to display for the "previous" link.
        next_text: The text to display for the "next" link.
        spacer_text: The text to display for "spacers" between nonconsecutive pages.
        always_show_prev_text: If true, then a <prev_text> entry will always be included. If there
            is no previous page, it will be given a None link (see Returns).
        always_show_next_text: If true, then a <next_text> entry will always be included. If there
            is no next page, it will be given a None page (see Returns).

    Returns:
        A tuple with two elements, the items on the current page and a list of tuples
        representing the links.

        The items are obtained by slicing the original ``items`` container.

        Each item in the links list is a 2-tuple with 1) the text that should be displayed and
        2) the integer number of the page it should link to, or None if the text should simply be
        displayed literally.

    """

    paginator = Paginator(items, per_page)
    page_num = max(1, min(paginator.num_pages, page_num))
    page = paginator.page(page_num)

    page_links: List[Tuple[str, Optional[int]]] = []
    if page.has_previous():
        page_links.append((prev_text, page.previous_page_number()))

        for i in range(1, min(num_start + 1, page_num - num_around)):
            page_links.append((str(i), i))

        if num_start + 1 < page_num - num_around:
            page_links.append((spacer_text, None))
    else:
        if always_show_prev_text:
            page_links.append((prev_text, None))

    for i in range(max(page_num - num_around, 1), page_num):
        page_links.append((str(i), i))

    page_links.append((str(page_num), (page_num if current_link else None)))

    for i in range(page_num + 1, min(page_num + num_around, paginator.num_pages) + 1):
        page_links.append((str(i), i))

    if page.has_next():
        if paginator.num_pages - num_end > page_num + num_around:
            page_links.append((spacer_text, None))

        for i in range(
            max(paginator.num_pages - num_end, page_num + num_around) + 1, paginator.num_pages + 1
        ):
            page_links.append((str(i), i))

        page_links.append((next_text, page.next_page_number()))
    else:
        if always_show_next_text:
            page_links.append((next_text, None))

    return items[max(page.start_index() - 1, 0): page.end_index()], page_links
