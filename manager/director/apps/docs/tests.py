import math
import uuid
from unittest.mock import mock_open, patch

from django.urls import reverse

from ...test.director_test import DirectorTestCase
from .utils import (
    find_static_file,
    get_page_title,
    load_doc_page,
    rewrite_markdown_link,
    url_to_path,
)


class DocsTestCase(DirectorTestCase):
    def test_doc_page_view(self):
        self.login()

        # We're going to patch the load_doc_page() call to get
        # the content I want
        header_magic_text = str(uuid.uuid4())
        with patch(
            "director.apps.docs.views.load_doc_page",
            return_value=({}, f"<h1>{header_magic_text}</h1>"),
        ) as mock_obj:
            response = self.client.get(
                reverse("docs:doc_page", kwargs={"url": "index"}) + "/", follow=True
            )

        mock_obj.assert_called()
        self.assertEqual(200, response.status_code)
        self.assertIn(header_magic_text, response.content.decode("UTF-8"))

    def test_search_view(self):
        self.login()

        # We're going to patch the load_doc_page() call to get
        # the content I want
        header_magic_text = str(uuid.uuid4())
        with patch(
            "director.apps.docs.views.load_doc_page",
            return_value=({}, f"<h1>{header_magic_text}</h1>"),
        ) as mock_obj:
            with patch(
                "director.apps.docs.views.iter_page_names", return_value=["hello"]
            ) as mock_iter_obj:
                response = self.client.get(
                    reverse("docs:search"), follow=True, data={"q": header_magic_text}
                )

        self.assertIn(("hello", "Hello", 1), response.context["results"])
        mock_obj.assert_called()
        mock_iter_obj.assert_called()


class DocsUtilsTestCase(DirectorTestCase):
    def test_rewrite_markdown_link(self):
        self.assertEqual(
            "/check/",
            rewrite_markdown_link(
                link_url="check.md", base_page_name="check", add_docs_prefix=False
            ),
        )
        self.assertEqual(
            "/check/",
            rewrite_markdown_link(link_url="check", base_page_name="check", add_docs_prefix=False),
        )
        self.assertEqual(
            "/check/",
            rewrite_markdown_link(link_url="check", base_page_name="/check", add_docs_prefix=False),
        )
        self.assertEqual(
            "/check/",
            rewrite_markdown_link(
                link_url="/check", base_page_name="/check", add_docs_prefix=False
            ),
        )
        self.assertEqual(
            "/check.html",
            rewrite_markdown_link(
                link_url="check.html", base_page_name="check", add_docs_prefix=False
            ),
        )
        self.assertEqual(
            "mailto:test@example.com",
            rewrite_markdown_link(
                link_url="mailto:test@example.com", base_page_name="", add_docs_prefix=True
            ),
        )

    def test_url_to_path(self):
        self.assertIsNone(url_to_path("https://director.tjhsst.edu/../../../../etc/passwd"))
        self.assertIsNone(url_to_path("https://director.tjhsst.edu/etc/passwd/.git/"))
        self.assertIsNotNone(url_to_path("https://director.tjhsst.edu/etc/passwd/"))

    def test_load_doc_page(self):
        with patch("builtins.open", mock_open(read_data="# hello")):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getmtime", return_value=math.inf):
                    html = load_doc_page("hello.md")

        self.assertIn("<h1", html[1])
        self.assertIn(">hello", html[1])

    def test_find_static_file(self):
        self.assertIsNone(find_static_file("/.././../../../../"))

        with self.settings(DIRECTOR_DOCS_DIR="/testing"):
            self.assertEqual("/testing/hello.html", find_static_file("hello.html"))

    def test_get_page_title(self):
        self.assertEqual(
            "hello this is a test",
            get_page_title(
                page_name="hello this is a test",
                metadata={"title": ["hello", "this", "is", "a", "test"]},
            ),
        )
        self.assertEqual(
            "Hello This Is A Test", get_page_title(page_name="hello this is a test", metadata={})
        )
        self.assertEqual("Howto", get_page_title(page_name="/custom-domains/howto", metadata={}))
