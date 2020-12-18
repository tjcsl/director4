from django.urls import reverse

from ....test.director_test import DirectorTestCase
from ..models import DockerImage, Site


class FilesTest(DirectorTestCase):
    def setUp(self):
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

    def test_editor_view(self):
        response = self.client.get(
            reverse("sites:editor", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(200, response.status_code)

    def test_get_file_view(self):
        response = self.client.get(
            reverse("sites:get_file", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.get(
            reverse("sites:get_file", kwargs={"site_id": self.site.id}),
            follow=True,
            data={"path": "/site/this_might_exist.txt"},
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_download_zip_view(self):
        response = self.client.get(
            reverse("sites:download_zip", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.get(
            reverse("sites:download_zip", kwargs={"site_id": self.site.id}),
            follow=True,
            data={"path": "/site/"},
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_write_file_view(self):
        response = self.client.post(
            reverse("sites:write_file", kwargs={"site_id": self.site.id}),
            follow=True,
            data={"path": "/site/hello.txt"},
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_create_file_view(self):
        response = self.client.post(
            reverse("sites:create_file", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.post(
            reverse("sites:create_file", kwargs={"site_id": self.site.id})
            + "?path=/site/hello.txt",
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_remove_file_view(self):
        response = self.client.post(
            reverse("sites:remove_file", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.post(
            reverse("sites:remove_file", kwargs={"site_id": self.site.id})
            + "?path=/site/hello.txt",
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_remove_directory_recur_view(self):
        response = self.client.post(
            reverse("sites:remove_directory_recur", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.post(
            reverse("sites:remove_directory_recur", kwargs={"site_id": self.site.id})
            + "?path=/site/public/",
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_make_directory_view(self):
        response = self.client.post(
            reverse("sites:mkdir", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.post(
            reverse("sites:mkdir", kwargs={"site_id": self.site.id}) + "?path=/site/public/",
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_chmod_view(self):
        response = self.client.post(
            reverse("sites:chmod", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` and `mode` not supplied

        response = self.client.post(
            reverse("sites:chmod", kwargs={"site_id": self.site.id}) + "?path=/site/public/",
            follow=True,
        )
        self.assertEqual(400, response.status_code)  # `mode` not supplied

        response = self.client.post(
            reverse("sites:chmod", kwargs={"site_id": self.site.id}) + "?mode=520", follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.post(
            reverse("sites:chmod", kwargs={"site_id": self.site.id})
            + "?path=/site/public/&mode=500",
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # no appservers online

    def test_rename_view(self):
        response = self.client.post(
            reverse("sites:rename", kwargs={"site_id": self.site.id}), follow=True
        )
        self.assertEqual(400, response.status_code)  # `path` and `mode` not supplied

        response = self.client.post(
            reverse("sites:rename", kwargs={"site_id": self.site.id}) + "?oldpath=/site/public/",
            follow=True,
        )
        self.assertEqual(400, response.status_code)  # `mode` not supplied

        response = self.client.post(
            reverse("sites:rename", kwargs={"site_id": self.site.id}) + "?newpath=/site/public21",
            follow=True,
        )
        self.assertEqual(400, response.status_code)  # `path` not supplied

        response = self.client.post(
            reverse("sites:rename", kwargs={"site_id": self.site.id})
            + "?oldpath=/site/public/&newpath=/site/public21",
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # no appservers online
