from django.urls import reverse

from ...test.director_test import DirectorTestCase


class ShellServerTestCase(DirectorTestCase):
    def test_authenticate_view(self):
        self.login(username="awilliam", accept_guidelines=True)

        # I'm not waiting 15 seconds for this test to complete
        with self.settings(SHELL_AUTH_KINIT_TIMEOUT=1):
            response = self.client.post(
                reverse("shell_server:authenticate"),
                data={"username": "awilliam", "password": "test"},
            )

        self.assertEqual(401, response.status_code)
