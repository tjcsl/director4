# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth import get_user_model
from django.urls import reverse

from ...test.director_test import DirectorTestCase


class UsersTestCase(DirectorTestCase):
    def test_mass_email_view(self):
        self.login(make_admin=True, accept_guidelines=True)

        get_user_model().objects.get_or_create(username="awilliam")

        response = self.client.get(reverse("users:mass_email"))
        self.assertEqual(200, response.status_code)

        response = self.client.post(
            reverse("users:mass_email"),
            data={
                "confirm_send": True,
                "subject": "This is a test",
                "text_html": "<p>hi</p>",
                "text_plain": "hi",
            },
            follow=True,
        )
        self.assertEqual(200, response.status_code)
