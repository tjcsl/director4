from unittest.mock import patch

from django.contrib.messages import get_messages
from django.urls import reverse

from director.apps.sites import operations
from director.apps.sites.models import Action, DockerImage, Operation, Site, SiteResourceLimits
from director.test.director_test import DirectorTestCase


class MaintenanceTest(DirectorTestCase):
    def setUp(self):
        self.login(accept_guidelines=True, make_admin=True, make_student=True)
        docker_image = DockerImage.objects.create(name="alpine:latest", is_custom=False)
        self.site = Site.objects.create(
            name="Sysadmins", type="dynamic", purpose="activity", docker_image=docker_image
        )

    def test_prometheus_metrics_view(self):
        response = self.client.get(reverse("sites:prometheus-metrics"))
        self.assertEqual(200, response.status_code)
        self.assertIn("director4_sites_failed_actions 0", str(response.content))

        self.client.logout()
        response = self.client.get(reverse("sites:prometheus-metrics"))
        self.assertNotEqual(200, response.status_code)  # Shouldn't be 200
        self.assertNotIn("director4_sites_failed_actions 0", str(response.content))

    def test_management_view(self):
        response = self.client.get(reverse("sites:management"))
        self.assertEqual(200, response.status_code)

    def test_operations_view(self):
        response = self.client.get(reverse("sites:operations"))
        self.assertEqual(200, response.status_code)
        self.assertEqual("Operations", response.context["title"])
        self.assertEqual(0, len(response.context["operations"]))

        operation = Operation.objects.create(site=self.site, type="fix_site")

        response = self.client.get(reverse("sites:operations"))
        self.assertEqual(200, response.status_code)
        self.assertEqual("Operations", response.context["title"])
        self.assertEqual(1, len(response.context["operations"]))
        self.assertIn(operation, response.context["operations"])

        response = self.client.get(reverse("sites:operations"), data={"failed": "failed"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("Failed Operations", response.context["title"])
        self.assertEqual(0, len(response.context["operations"]))
        self.assertNotIn(operation, response.context["operations"])

        action = Action.objects.create(operation=operation, slug="restart_site", result=False)

        # Now that there is a failed action, this should return something
        response = self.client.get(reverse("sites:operations"), data={"failed": "failed"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("Failed Operations", response.context["title"])
        self.assertEqual(1, len(response.context["operations"]))
        self.assertIn(operation, response.context["operations"])

        action.delete()
        operation.delete()

    def test_operation_delete_fix_view(self):
        operation = Operation.objects.create(site=self.site, type="fix_site")

        # The operation has not failed, so this should fail
        response = self.client.get(
            reverse("sites:operation-delete-fix", kwargs={"operation_id": operation.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Can only delete failed operations", messages)

        # Now, fail the operation and try again
        Action.objects.create(operation=operation, slug="restart_site", result=False)

        response = self.client.get(
            reverse("sites:operation-delete-fix", kwargs={"operation_id": operation.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertNotIn("Can only delete failed operations", messages)

        self.assertEqual(0, len(Operation.objects.filter(id=operation.id)))
        self.assertEqual(1, len(Operation.objects.filter(site=self.site)))

        operation = Operation.objects.get(site=self.site)
        self.assertEqual("fix_site", operation.type)

    def test_custom_resource_limits_list_view(self):
        response = self.client.get(reverse("sites:custom_resource_limits_list"), follow=True)
        self.assertEqual(
            0, len(response.context["custom_limit_sites"])
        )  # no sites have custom limits yet

        SiteResourceLimits.objects.create(site=self.site, cpus=3)

        response = self.client.get(reverse("sites:custom_resource_limits_list"), follow=True)
        self.assertEqual(1, len(response.context["custom_limit_sites"]))  # just added a site

        self.assertIn(self.site, response.context["custom_limit_sites"])

    def test_resource_limits_view(self):
        response = self.client.get(
            reverse("sites:resource_limits", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(200, response.status_code)

        with patch("director.apps.sites.operations.update_resource_limits") as patch_limits:
            response = self.client.post(
                reverse("sites:resource_limits", kwargs={"site_id": self.site.id}),
                follow=True,
                data={"cpus": 3, "mem_limit": "100MB", "client_body_limit": "100M", "notes": "hi"},
            )
            patch_limits.assert_called_with(self.site, 3.0, "100MB", "100M", "hi")

        self.assertEqual(200, response.status_code)

    def test_resource_limits_operation(self):
        with patch("director.apps.sites.tasks.update_resource_limits_task.delay") as url_task_patch:
            operations.update_resource_limits(self.site, 3.0, "100MB", "100M", "hi")

        ops = Operation.objects.filter(site=self.site)
        self.assertEqual(1, len(ops))
        self.assertEqual("update_resource_limits", ops[0].type)
        url_task_patch.assert_called_with(ops[0].id, 3.0, "100MB", "100M", "hi")

    def test_availability_view(self):
        response = self.client.get(
            reverse("sites:availability", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(200, response.status_code)

        with patch("director.apps.sites.operations.update_availability") as patch_availability:
            response = self.client.post(
                reverse("sites:availability", kwargs={"site_id": self.site.id}),
                follow=True,
                data={"availability": "disabled"},
            )
            patch_availability.assert_called_with(self.site, "disabled")

        self.assertEqual(200, response.status_code)
