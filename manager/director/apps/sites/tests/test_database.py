from unittest.mock import patch

from django.urls import reverse

from ....test.director_test import DirectorTestCase
from .. import operations, tasks
from ..models import DatabaseHost, DockerImage, Operation, Site


class DatabaseTest(DirectorTestCase):
    def setUp(self):
        super()
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
        self.db_host = DatabaseHost.objects.create(
            hostname="director-postgres-test",
            port=1234,
            dbms="postgres",
            admin_username="test",
            admin_password="test",
        )

        response = self.client.get(reverse("sites:info", kwargs={"site_id": self.site.id}))
        self.assertEqual(200, response.status_code)

    def test_create_database_view(self):
        with patch("director.apps.sites.operations.create_database") as cd_patch:
            response = self.client.post(
                reverse("sites:create_database", kwargs={"site_id": self.site.id}),
                follow=True,
                data={"host": self.db_host.id},
            )
            self.assertEqual(200, response.status_code)
            cd_patch.assert_called_with(self.site, self.db_host)

    def test_create_database_operation(self):
        with patch("director.apps.sites.tasks.create_database_task.delay") as cdt_patch:
            operations.create_database(self.site, self.db_host)

        ops = Operation.objects.filter(site=self.site)
        self.assertEqual(1, len(ops))
        self.assertEqual("create_site_database", ops[0].type)
        cdt_patch.assert_called_with(ops[0].id, self.db_host.id)

    def test_delete_database_view(self):
        with patch("director.apps.sites.operations.delete_database") as dd_patch:
            response = self.client.post(
                reverse("sites:delete_database", kwargs={"site_id": self.site.id}),
                follow=True,
                data={"confim": self.site.name[:-1]},
            )
            dd_patch.assert_not_called()  # did not enter confirmation of site's name

            response = self.client.post(
                reverse("sites:delete_database", kwargs={"site_id": self.site.id}),
                follow=True,
                data={"confirm": self.site.name},
            )
            self.assertEqual(200, response.status_code)
            dd_patch.assert_called_with(self.site)

    def test_delete_database_operation(self):
        with patch("director.apps.sites.tasks.delete_database_task.delay") as ddt_patch:
            operations.delete_database(self.site)

        ops = Operation.objects.filter(site=self.site)
        self.assertEqual(1, len(ops))
        self.assertEqual("delete_site_database", ops[0].type)
        ddt_patch.assert_called_with(ops[0].id)

    def test_delete_database_task(self):
        assert self.site.database is None
        operation = Operation.objects.create(site=self.site, type="delete_site_database")
        tasks.delete_database_task(operation.id)
        self.assertEqual(0, len(Operation.objects.filter(site=self.site)))
