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
