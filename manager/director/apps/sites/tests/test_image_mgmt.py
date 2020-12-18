from django.urls import reverse

from ....test.director_test import DirectorTestCase
from ..models import DockerImage, DockerImageSetupCommand, Site


class ImageManagementTest(DirectorTestCase):
    def setUp(self):
        self.user = self.login(accept_guidelines=True, make_admin=True)
        ds1 = DockerImageSetupCommand.objects.create(
            name="[OS:Alpine] echo hi", command="echo hi", order=0
        )

        dockerimage = DockerImage.objects.create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )
        dockerimage.setup_commands.add(ds1)
        dockerimage.save()

        DockerImage.objects.create(
            name="debian:latest", friendly_name="Debian", is_custom=False, is_user_visible=True
        )

    def test_home_view(self):
        response = self.client.get(reverse("sites:image_mgmt:home"), follow=True)
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(response.context["images"]))
        self.assertEqual(1, len(response.context["setup_commands"]))

    def test_create_view(self):
        response = self.client.post(
            reverse("sites:image_mgmt:create"),
            follow=True,
            data={
                "name": "archlinux:latest",
                "friendly_name": "Arch Linux",
                "description": "A lightweight and flexible"
                "Linux® distribution that tries to Keep It Simple",
                "logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/"
                "Archlinux-icon-crystal-64.svg/"
                "1024px-Archlinux-icon-crystal-64.svg.png",
                "is_user_visible": True,
                "setup_commands": [],
                "install_command_prefix": "pacman -Sy --",
                "base_install_command": "",
                "run_script_template": "",
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(3, len(DockerImage.objects.all()))
        self.assertEqual(1, len(DockerImage.objects.filter(name="archlinux:latest")))

        response = self.client.get(reverse("sites:image_mgmt:create"), follow=True)
        self.assertEqual(200, response.status_code)

    def test_edit_view(self):
        response = self.client.get(
            reverse(
                "sites:image_mgmt:edit",
                kwargs={"image_id": DockerImage.objects.get(name="alpine:latest").id},
            ),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        response = self.client.post(
            reverse(
                "sites:image_mgmt:edit",
                kwargs={"image_id": DockerImage.objects.get(name="debian:latest").id},
            ),
            follow=True,
            data={
                "name": "debian:latest",
                "friendly_name": "Debian",
                "description": "Slow",
                "is_custom": False,
                "is_user_visible": True,
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Slow", DockerImage.objects.get(name="debian:latest").description)

    def test_delete_view(self):
        response = self.client.get(
            reverse(
                "sites:image_mgmt:delete",
                kwargs={"image_id": DockerImage.objects.get(name="alpine:latest").id},
            ),
            follow=True,
        )
        self.assertEqual(200, response.status_code)

        # Check what happens if a site has this Docker image
        # It should not be deleted
        site = Site.objects.create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=DockerImage.objects.get(name="alpine:latest"),
        )

        response = self.client.post(
            reverse(
                "sites:image_mgmt:delete",
                kwargs={"image_id": DockerImage.objects.get(name="alpine:latest").id},
            ),
            follow=True,
            data={"confirm": "alpine:latest"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(DockerImage.objects.get(name="alpine:latest"), response.context["image"])
        self.assertIn(site, response.context["image_sites"])
        self.assertEqual(1, len(Site.objects.filter(name="sysadmins")))

        site.delete()

        response = self.client.post(
            reverse(
                "sites:image_mgmt:delete",
                kwargs={"image_id": DockerImage.objects.get(name="alpine:latest").id},
            ),
            follow=True,
            data={"confirm": "alpine:latest"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(DockerImage.objects.filter(name="alpine:latest")))

    def test_setup_command_edit_create_view(self):
        response = self.client.get(reverse("sites:image_mgmt:setup_command_create"), follow=True)
        self.assertEqual(200, response.status_code)

        response = self.client.post(
            reverse("sites:image_mgmt:setup_command_create"),
            follow=True,
            data={"name": "[OS:Alpine] echo hithere", "command": "echo hithere", "order": 0},
        )
        self.assertEqual(200, response.status_code)
        self.assertGreaterEqual(len(DockerImageSetupCommand.objects.all()), 1)
        self.assertEqual(
            1, len(DockerImageSetupCommand.objects.filter(name="[OS:Alpine] echo hithere"))
        )

        response = self.client.post(
            reverse(
                "sites:image_mgmt:setup_command_edit",
                kwargs={
                    "command_id": DockerImageSetupCommand.objects.get(
                        name="[OS:Alpine] echo hithere"
                    ).id
                },
            ),
            follow=True,
            data={"name": "[OS:Alpine] echo hithere", "command": "echo hibye", "order": 0},
        )
        self.assertEqual(200, response.status_code)

        self.assertEqual(
            "echo hibye",
            DockerImageSetupCommand.objects.get(name="[OS:Alpine] echo hithere").command,
        )

    def test_setup_command_delete_view(self):
        response = self.client.get(
            reverse(
                "sites:image_mgmt:setup_command_delete",
                kwargs={
                    "command_id": DockerImageSetupCommand.objects.get(name="[OS:Alpine] echo hi").id
                },
            ),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(DockerImageSetupCommand.objects.filter(name="[OS:Alpine] echo hi")))

        response = self.client.post(
            reverse(
                "sites:image_mgmt:setup_command_delete",
                kwargs={
                    "command_id": DockerImageSetupCommand.objects.get(name="[OS:Alpine] echo hi").id
                },
            ),
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(DockerImageSetupCommand.objects.filter(name="[OS:Alpine] echo hi")))

        # Now, try to remove even if there is still a
        # Docker image (`alpine`) associated with the command
        response = self.client.post(
            reverse(
                "sites:image_mgmt:setup_command_delete",
                kwargs={
                    "command_id": DockerImageSetupCommand.objects.get(name="[OS:Alpine] echo hi").id
                },
            ),
            follow=True,
            data={"confirm": "[OS:Alpine] echo hi"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(DockerImageSetupCommand.objects.filter(name="[OS:Alpine] echo hi")))

        # Remove the command from the Docker image, then remove
        DockerImage.objects.get(name="alpine:latest").setup_commands.clear()
        response = self.client.post(
            reverse(
                "sites:image_mgmt:setup_command_delete",
                kwargs={
                    "command_id": DockerImageSetupCommand.objects.get(name="[OS:Alpine] echo hi").id
                },
            ),
            follow=True,
            data={"confirm": "[OS:Alpine] echo hi"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(DockerImageSetupCommand.objects.filter(name="[OS:Alpine] echo hi")))
