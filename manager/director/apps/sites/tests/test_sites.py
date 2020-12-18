import uuid

from django.contrib.messages import get_messages
from django.urls import reverse

from ....test.director_test import DirectorTestCase
from ..models import DockerImage, Site


class SitesTest(DirectorTestCase):
    def test_index_view(self):
        user2 = self.login(
            username="2020awilliam", accept_guidelines=True, make_admin=False, make_student=True
        )
        user = self.login(accept_guidelines=True, make_admin=True, make_teacher=True)
        response = self.client.get(reverse("sites:index"), follow=True)
        self.assertEqual(200, response.status_code)

        # There are no sites at the moment.
        self.assertEqual(0, len(response.context["paginated_sites"]))

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]
        site.users.add(user)
        site.save()

        response = self.client.get(reverse("sites:index"), follow=True)
        self.assertEqual(200, response.status_code)

        # There is now one site that I am a member of at the moment.
        self.assertEqual(1, len(response.context["paginated_sites"]))

        site2 = Site.objects.get_or_create(
            name="hello",
            description="test2",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]
        site2.users.add(user2)
        site2.save()

        response = self.client.get(reverse("sites:index"), follow=True)
        self.assertEqual(200, response.status_code)

        # There is still only one site that I am a member of at the moment.
        self.assertEqual(1, len(response.context["paginated_sites"]))
        self.assertIn(site, response.context["paginated_sites"])

        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"all": True},
        )
        self.assertEqual(200, response.status_code)

        # There are two sites that exist.
        self.assertEqual(2, len(response.context["paginated_sites"]))
        self.assertIn(site2, response.context["paginated_sites"])
        self.assertIn(site, response.context["paginated_sites"])

        # Add a boatload of sites.
        for _ in range(500):
            Site.objects.get_or_create(
                name=str(uuid.uuid4()).replace("-", ""),
                description=str(uuid.uuid4()),
                type="dynamic",
                purpose="activity",
                docker_image=dockerimage,
            )
            site2.users.add(user2)
            site2.save()

        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"page": "5", "all": "1"},
        )
        self.assertGreaterEqual(len(response.context["page_links"]), 7)
        self.assertEqual(200, response.status_code)

        # Now, test some search queries.
        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"q": "name:sysadmins"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.context["paginated_sites"]))
        self.assertIn(site, response.context["paginated_sites"])

        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"q": f"user:{user.username}"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.context["paginated_sites"]))
        self.assertIn(site, response.context["paginated_sites"])

        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"q": f"user:{user.username}"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.context["paginated_sites"]))
        self.assertIn(site, response.context["paginated_sites"])

        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"q": f"desc:{site2.description}"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.context["paginated_sites"]))
        self.assertIn(site2, response.context["paginated_sites"])

        response = self.client.get(
            reverse("sites:index"),
            follow=True,
            data={"q": f"id:{site2.id}"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.context["paginated_sites"]))
        self.assertIn(site2, response.context["paginated_sites"])

    def test_terminal_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]
        site.users.add(user)
        site.save()

        response = self.client.get(
            reverse("sites:terminal", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(site, response.context["site"])
        self.assertEqual("", response.context["command_str"])

    def test_regen_nginx_config_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]

        site.users.add(user)
        site.save()

        # Now, try to regenerate
        response = self.client.post(
            reverse("sites:regen_nginx_config", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        # Try to regenerate again and it should fail because an operation is already in progress
        response = self.client.post(
            reverse("sites:regen_nginx_config", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)  # Status code is still 200
        self.assertIn(
            "An operation is already being performed on this site",
            [message.message for message in get_messages(response.wsgi_request)],
        )

    def test_create_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        response = self.client.get(
            reverse("sites:create"),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        response = self.client.post(
            reverse("sites:create"),
            follow=True,
            data={
                "name": "test",
                "type": "dynamic",
                "purpose": "project",
                "users": user.id,
                "student_agreement": True,
            },
        )
        self.assertEqual(200, response.status_code)

        self.assertEqual(1, Site.objects.filter(name="test").count())

    def test_create_webdocs_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        response = self.client.get(reverse("sites:create_webdocs"))
        self.assertEqual(200, response.status_code)

        response = self.client.post(
            reverse("sites:create_webdocs"),
            follow=True,
            data={
                "name": "awilliam",
                "type": "dynamic",
                "purpose": "user",
                "users": user.id,
                "student_agreement": True,
            },
        )
        self.assertEqual(200, response.status_code)

        self.assertEqual(1, Site.objects.filter(name="awilliam", purpose="user").count())

        # If I try to create another site, I should get 302ed to the already created site
        response = self.client.get(reverse("sites:create_webdocs"))
        self.assertEqual(302, response.status_code)

        response = self.client.get(reverse("sites:create_webdocs"), follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(Site.objects.get(name="awilliam"), response.context["site"])

    def test_info_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)
        site = Site.objects.create(
            name="awilliam",
            purpose="user",
            type="dynamic",
            docker_image=DockerImage.objects.get_default_image(),
        )

        response = self.client.get(reverse("sites:info", kwargs={"site_id": site.id}))
        self.assertEqual(404, response.status_code)  # because the site does not have us as a user

        site.users.add(user)
        site.save()

        response = self.client.get(reverse("sites:info", kwargs={"site_id": site.id}))
        self.assertEqual(200, response.status_code)

    def test_image_select_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)
        site = Site.objects.create(
            name="awilliam",
            purpose="user",
            type="dynamic",
            docker_image=DockerImage.objects.get_default_image(),
        )
        site.users.add(user)
        site.save()

        dockerimage_arch = DockerImage.objects.get_or_create(
            name="archlinux:latest", friendly_name="Arch", is_custom=False, is_user_visible=True
        )[0]

        response = self.client.get(reverse("sites:image_select", kwargs={"site_id": site.id}))
        self.assertEqual(200, response.status_code)
        self.assertIn(
            dockerimage_arch, [x[1] for x in response.context["image_subwidgets_and_objs"]]
        )

        # Try to change the image to that Arch image
        response = self.client.post(
            reverse("sites:image_select", kwargs={"site_id": site.id}),
            follow=True,
            data={"image": "archlinux:latest", "write_run_sh_file": False, "packages": "python"},
        )
        self.assertEqual(200, response.status_code)

        # Loading the page again should fail
        response = self.client.get(reverse("sites:image_select", kwargs={"site_id": site.id}))
        self.assertEqual(302, response.status_code)  # back to info view

    def test_regenerate_secrets_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]

        site.users.add(user)
        site.save()

        # Now, try to regenerate
        response = self.client.post(
            reverse("sites:regenerate_secrets", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        # Try to regenerate again and it should fail because an operation is already in progress
        response = self.client.post(
            reverse("sites:regenerate_secrets", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)  # Status code is still 200
        self.assertIn(
            "An operation is already being performed on this site",
            [message.message for message in get_messages(response.wsgi_request)],
        )

    def test_restart_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]

        site.users.add(user)
        site.save()

        # Now, try to restart
        response = self.client.post(
            reverse("sites:restart_service", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        # Try to restart again and it should fail because an operation is already in progress
        response = self.client.post(
            reverse("sites:restart_service", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)  # Status code is still 200
        self.assertIn(
            "An operation is already being performed on this site",
            [message.message for message in get_messages(response.wsgi_request)],
        )

    def test_restart_raw_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]

        site.users.add(user)
        site.save()

        # Now, try to restart
        response = self.client.post(
            reverse("sites:restart_service_raw", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        # Try to restart again and it should fail because an operation is already in progress
        response = self.client.post(
            reverse("sites:restart_service_raw", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(500, response.status_code)  # Status code is still 200
        self.assertIn(
            "An operation is already being performed on this site",
            response.content.decode("UTF-8"),
        )

    def test_delete_view(self):
        user = self.login(accept_guidelines=True, make_admin=False, make_student=True)

        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]

        site.users.add(user)
        site.save()

        response = self.client.get(reverse("sites:delete", kwargs={"site_id": site.id}))
        self.assertEqual(200, response.status_code)

        # Now, try to delete
        response = self.client.post(
            reverse("sites:delete", kwargs={"site_id": site.id}),
            follow=True,
            data={"confirm": site.name},
        )
        self.assertEqual(200, response.status_code)

        # Try to delete again and it should fail because an operation is already in progress
        response = self.client.get(
            reverse("sites:delete", kwargs={"site_id": site.id}),
            follow=True,
        )
        self.assertEqual(200, response.status_code)  # Status code is still 200
        self.assertIn(
            "An operation is already being performed on this site",
            [message.message for message in get_messages(response.wsgi_request)],
        )
