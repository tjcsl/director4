# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.test import SimpleTestCase

from director.apps.sites.consumers import serialize_action_for_user
from director.apps.sites.models import Action


class SiteInfoActionSerializationTest(SimpleTestCase):
    def test_user_action_payload_omits_sensitive_fields(self) -> None:
        # An Action carrying detailed internal output in the fields that must stay admin-only.
        action = Action(
            slug="update_appserver_nginx_config",
            name="Updating appserver configuration",
            result=False,
            message="Error reloading Nginx config (`nginx -s reload` exited 1)",
            before_state="internal-before-state",
            after_state="internal-after-state",
        )

        data = serialize_action_for_user(action, "%Y-%m-%d %H:%M:%S %Z")

        # The site owner may only ever see these non-sensitive fields.
        self.assertEqual(set(data), {"slug", "name", "started_time", "result"})

        # The detailed / internal fields must never be propagated to the user side; they are
        # exposed only in the superuser operations panel. If a future refactor re-adds any of
        # these to the site-info payload, this test should fail.
        for sensitive_field in ("message", "before_state", "after_state"):
            self.assertNotIn(sensitive_field, data)
