# SPDX-License-Identifier: MIT
# (c) 2020 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import reverse

from ...test.director_test import DirectorTestCase


class AuthTest(DirectorTestCase):
    def test_accept_guidelines(self):
        # Log in as a user that has not accepted guidelines
        self.login(accept_guidelines=False)
        response = self.client.get(reverse("auth:index"), follow=True)
        self.assertIn("auth/accept_guidelines.html", [t.name for t in response.templates])
        self.assertEqual(200, response.status_code)

        # Log in as a user that has accept guidelines
        self.login(accept_guidelines=True)
        response = self.client.get(reverse("auth:index"), follow=True)
        self.assertNotIn("auth/accept_guidelines.html", [t.name for t in response.templates])
        self.assertEqual(200, response.status_code)

    def test_index_view(self):
        """
        Tests whether or not the index redirect if logged in or not works.
        Returns: None

        """
        # Logout
        self.client.logout()
        response = self.client.get(reverse("auth:index"), follow=True)
        self.assertIn("auth/login.html", [t.name for t in response.templates])
        self.assertEqual(200, response.status_code)

        # Login
        self.login(accept_guidelines=True)
        response = self.client.get(reverse("auth:index"), follow=True)
        self.assertNotIn("auth/login.html", [t.name for t in response.templates])
        self.assertEqual(200, response.status_code)

    def test_login_view(self):
        # Logout
        self.client.logout()
        response = self.client.get(reverse("auth:login"), follow=True)
        self.assertIn("auth/login.html", [t.name for t in response.templates])
        self.assertEqual(200, response.status_code)

    def test_logout_view(self):
        self.login(accept_guidelines=True)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.get(reverse("auth:logout"), follow=True)
        self.assertNotIn("_auth_user_id", self.client.session)
