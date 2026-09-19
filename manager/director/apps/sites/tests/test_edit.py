from django.urls import reverse

from ....test.director_test import DirectorTestCase
from ..models import DockerImage, Site


class EditTest(DirectorTestCase):
    def setUp(self):
        super()
        self.user2 = self.login(
            username="2020awilliam", accept_guidelines=True, make_admin=False, make_student=True
        )
        self.user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        self.site = Site.objects.create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=DockerImage.objects.get_default_image(),
        )
        self.site.users.add(self.user)
        self.site.save()

    def test_edit_view(self):
        response = self.client.get(
            reverse("sites:edit", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(200, response.status_code)

    def test_edit_meta_view(self):
        self.client.post(
            reverse("sites:edit_meta", kwargs={"site_id": self.site.id}),
            follow=True,
            data={
                "description": "this is a weird test",
                "purpose": "activity",
                "users": [self.user.id, self.user2.id],
            },
        )

        site = Site.objects.get(id=self.site.id)
        self.assertEqual("this is a weird test", site.description)
        self.assertEqual("activity", site.purpose)
        self.assertEqual(2, len(site.users.all()))
        self.assertIn(self.user, site.users.all())
        self.assertIn(self.user2, site.users.all())

    def test_non_superuser_cannot_remove_all_users(self):
        response = self.client.post(
            reverse("sites:edit_meta", kwargs={"site_id": self.site.id}),
            data={
                "description": "this change should not be saved",
                "purpose": "activity",
                "users": [],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertFormError(
            response.context["meta_form"],
            "users",
            "Only administrators can remove all users from a site",
        )

        self.site.refresh_from_db()
        self.assertEqual("test", self.site.description)
        self.assertEqual([self.user], list(self.site.users.all()))

    def test_superuser_can_remove_all_users(self):
        self.login(username="admin", accept_guidelines=True, make_admin=True)

        response = self.client.post(
            reverse("sites:edit_meta", kwargs={"site_id": self.site.id}),
            data={
                "description": "updated by an administrator",
                "purpose": "activity",
                "users": [],
            },
        )

        self.assertRedirects(response, reverse("sites:info", kwargs={"site_id": self.site.id}))

        self.site.refresh_from_db()
        self.assertEqual("updated by an administrator", self.site.description)
        self.assertFalse(self.site.users.exists())
