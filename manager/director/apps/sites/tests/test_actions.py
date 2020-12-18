import json
import uuid
from unittest.mock import patch

from ....test.director_test import DirectorTestCase
from ....utils.appserver import AppserverConnectionError, AppserverProtocolError
from ....utils.balancer import BalancerProtocolError
from ..actions import (
    build_docker_image,
    create_real_site_database,
    delete_site_database_and_object,
    ensure_site_directories_exist,
    find_pingable_appservers,
    regen_database_password,
    remove_all_site_files_dangerous,
    remove_appserver_nginx_config,
    remove_balancer_nginx_config,
    remove_docker_image,
    remove_docker_service,
    restart_docker_service,
    update_appserver_nginx_config,
    update_balancer_certbot,
    update_balancer_nginx_config,
    update_docker_service,
)
from ..models import Database, DatabaseHost, DockerImage, Site


class ActionsTestCase(DirectorTestCase):
    def setUp(self):
        dockerimage = DockerImage.objects.get_or_create(
            name="alpine:latest", friendly_name="Alpine", is_custom=False, is_user_visible=True
        )[0]

        self.site = Site.objects.get_or_create(
            name="sysadmins",
            description="test",
            type="dynamic",
            purpose="activity",
            docker_image=dockerimage,
        )[0]

    def test_find_pingable_appservers(self):
        with patch(
            "director.apps.sites.actions.iter_pingable_appservers", return_value=iter([1, 2, 3, 5])
        ) as mock_ping:
            result = find_pingable_appservers(self.site, {})  # type: ignore

            self.assertEqual("Pinging appservers", next(result))
            self.assertEqual("Pingable appservers: [1, 2, 3, 5]", next(result))

            mock_ping.assert_called()

    def test_update_appserver_nginx_config(self):
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = update_appserver_nginx_config(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual("Connecting to appserver 0 to update Nginx config", next(result))
            self.assertEqual("Error updating Nginx config", next(result))
            self.assertEqual("Disabling site Nginx config", next(result))

            with self.assertRaises(AppserverProtocolError):
                self.assertEqual("Re-raising exception", next(result))

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=None
        ) as mock_req:
            result = update_appserver_nginx_config(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Connecting to appserver 0 to update Nginx config", next(result))
            self.assertEqual("Successfully updated Nginx config", next(result))
            self.assertEqual("Reloading Nginx config on all appservers", next(result))
            self.assertEqual("Reloading Nginx config on appserver 0", next(result))
            self.assertEqual("Successfully reloaded configuration", next(result))

            mock_req.assert_called()

    def test_remove_appserver_nginx_config(self):
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = remove_appserver_nginx_config(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual("Connecting to appserver 0 to remove Nginx config", next(result))

            with self.assertRaises(AppserverProtocolError):
                next(result)

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=None
        ) as mock_req:
            result = remove_appserver_nginx_config(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Connecting to appserver 0 to remove Nginx config", next(result))
            self.assertEqual("Reloading Nginx config on all appservers", next(result))
            self.assertEqual("Reloading Nginx config on appserver 0", next(result))
            self.assertEqual("Done", next(result))

            mock_req.assert_called()

    def test_update_docker_service(self):
        # First, make sure that a disabled site removes the Docker service
        magic_str = str(uuid.uuid4())
        with patch(
            "director.apps.sites.actions.remove_docker_service", return_value=iter([magic_str])
        ) as mock_remove:
            self.site.availability = "disabled"
            self.site.save()

            result = update_docker_service(self.site, {"pingable_appservers": [0]})
            self.assertEqual(magic_str, next(result))
            mock_remove.assert_called()

        self.site.availability = "enabled"
        self.site.save()

        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = update_docker_service(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual(
                "Connecting to appserver 0 to create/update Docker service", next(result)
            )

            with self.assertRaises(AppserverProtocolError):
                next(result)

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=None
        ) as mock_req:
            result = update_docker_service(self.site, {"pingable_appservers": [0]})

            self.assertEqual(
                "Connecting to appserver 0 to create/update Docker service", next(result)
            )
            self.assertEqual("Created/updated Docker service", next(result))

            mock_req.assert_called()

    def test_restart_docker_service(self):
        # First, make sure that a disabled site does nothing
        self.site.availability = "disabled"
        self.site.save()

        result = restart_docker_service(self.site, {"pingable_appservers": [0]})
        self.assertEqual("Site disabled; skipping", next(result))

        self.site.availability = "enabled"
        self.site.save()

        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = restart_docker_service(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual("Connecting to appserver 0 to restart Docker service", next(result))

            with self.assertRaises(AppserverProtocolError):
                next(result)

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=None
        ) as mock_req:
            result = restart_docker_service(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Connecting to appserver 0 to restart Docker service", next(result))
            self.assertEqual("Restarted Docker service", next(result))

            mock_req.assert_called_once_with(
                0, f"/sites/{self.site.id}/restart-docker-service", method="POST"
            )

    def test_remove_docker_service(self):
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = remove_docker_service(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual("Connecting to appserver 0 to remove Docker service", next(result))

            with self.assertRaises(AppserverProtocolError):
                next(result)

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=None
        ) as mock_req:
            result = remove_docker_service(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Connecting to appserver 0 to remove Docker service", next(result))
            self.assertEqual("Removed Docker service", next(result))

            mock_req.assert_called_once_with(
                0, f"/sites/{self.site.id}/remove-docker-service", method="POST"
            )

    def test_build_docker_image(self):
        # self.site does not have a custom Docker image, currently
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = build_docker_image(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Site does not have a custom Docker image; skipping", next(result))

        # Make self.site.docker_image a custom one for this
        self.site.docker_image.is_custom = True
        self.site.docker_image.save()

        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = build_docker_image(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Connecting to appserver 0 to build Docker image", next(result))

            # appserver 0 is not reachable
            with self.assertRaises(Exception):
                next(result)

    def test_remove_docker_image(self):
        # self.site does not have a custom Docker image, currently
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = remove_docker_image(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Site does not have a custom Docker image; skipping", next(result))

        # Make self.site.docker_image a custom one for this
        self.site.docker_image.is_custom = True
        self.site.docker_image.save()

        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = remove_docker_image(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual("Removing Docker image on appserver 0", next(result))

            with self.assertRaises(AppserverProtocolError):
                next(result)

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=True
        ) as mock_req:
            result = remove_docker_image(self.site, {"pingable_appservers": [0]})

            self.assertEqual("Removing Docker image on appserver 0", next(result))
            self.assertEqual("Removing Docker image from registry on appserver 0", next(result))

            mock_req.assert_called_with(
                0, "/sites/remove-docker-image", method="POST", params={"name": "alpine:latest"}
            )

            try:
                next(result)
            except StopIteration:
                pass

            mock_req.assert_called_with(
                0, "/sites/remove-registry-image", method="POST", params={"name": "alpine:latest"}
            )

    def test_ensure_site_directories_exist(self):
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = ensure_site_directories_exist(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual(
                "Connecting to appserver 0 to ensure site directories exist", next(result)
            )

            with self.assertRaises(AppserverProtocolError):
                next(result)

        # Now, patch that method to bypass it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=True
        ) as mock_req:
            result = ensure_site_directories_exist(self.site, {"pingable_appservers": [0]})

            self.assertEqual(
                "Connecting to appserver 0 to ensure site directories exist", next(result)
            )

            try:
                next(result)
            except StopIteration:
                pass

            mock_req.assert_called_with(
                0, f"/sites/{self.site.id}/ensure-directories-exist", method="POST"
            )

    def test_remove_all_site_files_dangerous(self):
        with self.settings(DIRECTOR_APPSERVER_HOSTS=["director-apptest1:8000"]):
            result = remove_all_site_files_dangerous(self.site, {"pingable_appservers": [0]})

            # "director-apptest1:8000" obviously isn't pingable.
            self.assertEqual("Connecting to appserver 0 to remove site files", next(result))

            try:
                next(result)

                # If this test works, then we must have been passed to the try-catch.
                # The false assertion below serves to fail the test if we are not
                # in the try-catch.
                self.assertFalse(True)  # pylint: disable=redundant-unittest-assert
            except (OSError, ConnectionRefusedError):
                pass

    def test_update_balancer_nginx_config(self):
        with self.settings(
            DIRECTOR_BALANCER_HOSTS=["director-baltest1:8000"], DIRECTOR_NUM_BALANCERS=1
        ):
            with patch("director.apps.sites.actions.iter_pingable_balancers", return_value=[0]):
                result = update_balancer_nginx_config(self.site, {})

                # "director-baltest1:8000" obviously isn't pingable, but we patch it here.
                self.assertEqual("Pinging balancers", next(result))
                self.assertEqual("Pingable balancers: [0]", next(result))
                self.assertEqual("Updating balancer 0", next(result))

                with self.assertRaises(BalancerProtocolError):
                    next(result)

                # Now, patch that method to bypass it
                with patch(
                    "director.apps.sites.actions.balancer_open_http_request", return_value=True
                ) as mock_req:
                    result = update_balancer_nginx_config(self.site, {})

                    self.assertEqual("Pinging balancers", next(result))
                    self.assertEqual("Pingable balancers: [0]", next(result))
                    self.assertEqual("Updating balancer 0", next(result))
                    self.assertEqual("Updated balancer 0", next(result))

                    mock_req.assert_called_with(
                        0,
                        f"/sites/{self.site.id}/update-nginx",
                        method="POST",
                        data={"data": json.dumps(self.site.serialize_for_balancer())},
                    )

    def test_remove_balancer_nginx_config(self):
        with self.settings(
            DIRECTOR_BALANCER_HOSTS=["director-baltest1:8000"], DIRECTOR_NUM_BALANCERS=1
        ):
            with patch("director.apps.sites.actions.iter_pingable_balancers", return_value=[0]):
                result = remove_balancer_nginx_config(self.site, {})

                # "director-baltest1:8000" obviously isn't pingable, but we patch it here.
                self.assertEqual("Pinging balancers", next(result))
                self.assertEqual("Pingable balancers: [0]", next(result))
                self.assertEqual("Removing Nginx config on balancer 0", next(result))

                with self.assertRaises(BalancerProtocolError):
                    next(result)

                # Now, patch that method to bypass it
                with patch(
                    "director.apps.sites.actions.balancer_open_http_request", return_value=True
                ) as mock_req:
                    result = remove_balancer_nginx_config(self.site, {})

                    self.assertEqual("Pinging balancers", next(result))
                    self.assertEqual("Pingable balancers: [0]", next(result))
                    self.assertEqual("Removing Nginx config on balancer 0", next(result))
                    self.assertEqual("Removed Nginx config on balancer 0", next(result))

                    mock_req.assert_called_with(
                        0, f"/sites/{self.site.id}/remove-nginx", method="POST"
                    )

    def test_update_balancer_certbot(self):
        with self.settings(
            DIRECTOR_BALANCER_HOSTS=["director-baltest1:8000"], DIRECTOR_NUM_BALANCERS=1
        ):
            with patch("director.apps.sites.actions.iter_pingable_balancers", return_value=[0]):
                result = update_balancer_certbot(self.site, {})

                # "director-baltest1:8000" obviously isn't pingable, but we patch it here.
                self.assertEqual("Setting up certbot for site", next(result))

                with self.assertRaises(BalancerProtocolError):
                    next(result)

                # Now, patch that method to bypass it
                with patch(
                    "director.apps.sites.actions.balancer_open_http_request", return_value=True
                ) as mock_req:
                    result = update_balancer_certbot(self.site, {})

                    self.assertEqual("Setting up certbot for site", next(result))
                    self.assertEqual("Removing old domains", next(result))

                    mock_req.assert_called_with(
                        0,
                        f"/sites/{self.site.id}/certbot-setup",
                        method="POST",
                        data={"data": json.dumps(self.site.serialize_for_balancer())},
                    )

    def test_delete_site_database_and_object(self):
        # The site doesn't have a database object yet.
        with self.assertRaises(AssertionError):
            next(delete_site_database_and_object(site=self.site, scope={}))

        dbhost = DatabaseHost.objects.create(hostname="test-postgres", port=5432, dbms="postgres")

        database = Database.objects.create(host=dbhost, password="x")
        self.site.database = database
        self.site.save()

        result = delete_site_database_and_object(site=self.site, scope={"pingable_appservers": [0]})

        self.assertEqual("Connecting to appserver 0 to delete real database", next(result))
        with self.assertRaises(AppserverConnectionError):
            next(result)

        # Patch it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=True
        ) as mock_req:
            result = delete_site_database_and_object(
                site=self.site, scope={"pingable_appservers": [0]}
            )

            self.assertEqual("Connecting to appserver 0 to delete real database", next(result))
            self.assertEqual("Deleting database object in model", next(result))

            try:
                next(result)
            except StopIteration:
                pass

            mock_req.assert_called_once_with(
                0,
                "/sites/databases/delete",
                method="POST",
                data={"data": json.dumps(self.site.database.serialize_for_appserver())},
                timeout=30,
            )

            self.assertIsNone(Site.objects.get(id=self.site.id).database)

    def test_create_real_site_database(self):
        # The site doesn't have a database object yet.
        with self.assertRaises(AssertionError):
            next(delete_site_database_and_object(site=self.site, scope={}))

        dbhost = DatabaseHost.objects.create(hostname="test-postgres", port=5432, dbms="postgres")

        database = Database.objects.create(host=dbhost, password="x")
        self.site.database = database
        self.site.save()

        result = create_real_site_database(site=self.site, scope={"pingable_appservers": [0]})

        self.assertEqual("Connecting to appserver 0 to create real site database", next(result))
        with self.assertRaises(AppserverConnectionError):
            next(result)

        # Patch it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=True
        ) as mock_req:
            result = create_real_site_database(site=self.site, scope={"pingable_appservers": [0]})

            self.assertEqual("Connecting to appserver 0 to create real site database", next(result))

            try:
                next(result)
            except StopIteration:
                pass

            mock_req.assert_called_once_with(
                0,
                "/sites/databases/create",
                method="POST",
                data={"data": json.dumps(self.site.database.serialize_for_appserver())},
                timeout=30,
            )

    def test_regen_database_password(self):
        # The site doesn't have a database object yet.
        with self.assertRaises(AssertionError):
            next(delete_site_database_and_object(site=self.site, scope={}))

        dbhost = DatabaseHost.objects.create(hostname="test-postgres", port=5432, dbms="postgres")

        database = Database.objects.create(host=dbhost, password="x")
        self.site.database = database
        self.site.save()

        result = regen_database_password(site=self.site, scope={"pingable_appservers": [0]})

        self.assertEqual("Updating password in database model", next(result))
        self.assertEqual("Connecting to appserver 0 to update real password", next(result))
        with self.assertRaises(AppserverConnectionError):
            next(result)

        new_password = Database.objects.get(id=database.id).password
        self.assertNotEqual("x", new_password)

        # Patch it
        with patch(
            "director.apps.sites.actions.appserver_open_http_request", return_value=True
        ) as mock_req:
            result = regen_database_password(site=self.site, scope={"pingable_appservers": [0]})

            self.assertEqual("Updating password in database model", next(result))
            self.assertEqual("Connecting to appserver 0 to update real password", next(result))

            try:
                next(result)
            except StopIteration:
                pass

            mock_req.assert_called_once_with(
                0,
                "/sites/databases/create",
                method="POST",
                data={"data": json.dumps(self.site.database.serialize_for_appserver())},
                timeout=30,
            )

            new_new_password = Database.objects.get(id=database.id).password
            self.assertNotEqual(new_password, new_new_password)
