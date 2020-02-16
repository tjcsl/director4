# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
# pylint: disable=unused-variable

import random
from typing import Any, Dict, Iterator, List, Tuple, Union

from celery import shared_task

from django.conf import settings
from django.contrib.auth import get_user_model

from ...utils import database as database_utils
from ...utils.appserver import appserver_open_http_request
from ...utils.secret_generator import gen_database_password
from . import actions
from .helpers import auto_run_operation_wrapper
from .models import (
    Database,
    DatabaseHost,
    DockerImage,
    DockerImageExtraPackage,
    Domain,
    Site,
    SiteResourceLimits,
)


@shared_task
def rename_site_task(operation_id: int, new_name: str) -> None:
    scope: Dict[str, Any] = {"new_name": new_name}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        @wrapper.add_action("Changing site name in database")
        def change_site_name(
            site: Site, scope: Dict[str, Any]
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield ("before_state", site.name)

            site.name = scope["new_name"]
            site.save(update_fields=["name"])

            yield ("after_state", site.name)

        wrapper.add_action(
            "Updating appserver configuration", actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action(
                "Updating balancer configuration", actions.update_balancer_nginx_config
            )


@shared_task
def edit_site_names_task(
    operation_id: int, *, new_name: str, domains: List[str], request_username: str,
) -> None:
    scope: Dict[str, Any] = {
        "new_name": new_name,
        "domains": domains,
        "request_username": request_username,
    }

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        @wrapper.add_action("Changing site name in database")
        def change_site_name(
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield ("before_state", site.name)

            site.name = scope["new_name"]
            site.save(update_fields=["name"])

            yield ("after_state", site.name)

        @wrapper.add_action("Setting site domain names in database")
        def change_site_domains(
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield ("before_state", str(site.list_urls()))

            request_user = get_user_model().objects.get(username=scope["request_username"])

            for domain_name in scope["domains"]:
                try:
                    domain_obj = Domain.objects.get(domain=domain_name)
                    if domain_obj.site is not None and domain_obj.site.id != site.id:
                        yield "Domain {} belongs to another site; silently ignoring".format(
                            domain_name,
                        )
                    else:
                        yield "Domain {} already belongs to site {}".format(domain_name, site.id)
                except Domain.DoesNotExist:
                    Domain.objects.create(site=site, domain=domain_name, creating_user=request_user)

            site.domain_set.exclude(domain__in=scope["domains"]).delete()

            yield ("after_state", str(site.list_urls()))

        wrapper.add_action(
            "Updating appserver configuration", actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action(
                "Updating balancer configuration", actions.update_balancer_nginx_config
            )


@shared_task
def regen_nginx_config_task(operation_id: int) -> None:
    scope: Dict[str, Any] = {}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        wrapper.add_action(
            "Updating appserver configuration", actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action(
                "Updating balancer configuration", actions.update_balancer_nginx_config
            )


@shared_task
def create_database_task(operation_id: int, database_host_id: int) -> None:
    scope: Dict[str, Any] = {"database_host": DatabaseHost.objects.get(id=database_host_id)}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        @wrapper.add_action("Creating database object")
        def create_database_object(
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield ("before_state", "<nonexistent>")

            database_host = scope["database_host"]

            database = Database.objects.create(host=database_host, password=gen_database_password())
            site.database = database
            site.save()

            yield ("after_state", "host={}".format(database_host.hostname))

        @wrapper.add_action("Creating real database")
        def create_real_database(  # pylint: disable=unused-argument
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield "Creating real database"

            assert site.database is not None

            database_utils.create_database(site.database)

        wrapper.add_action("Updating Docker service", actions.update_docker_service)


@shared_task
def update_resource_limits_task(operation_id: int, cpus: float, mem_limit: str, notes: str) -> None:
    scope: Dict[str, Any] = {"cpus": cpus, "mem_limit": mem_limit, "notes": notes}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        @wrapper.add_action("Updating SiteResourceLimits object")
        def update_resource_limits_object(
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            if SiteResourceLimits.objects.filter(site=site).exists():
                yield ("before_state", str(site.resource_limits))
            else:
                yield ("before_state", "<nonexistent>")
                SiteResourceLimits.objects.create(site=site)

            site.resource_limits.cpus = scope["cpus"]
            site.resource_limits.mem_limit = scope["mem_limit"]
            site.resource_limits.notes = scope["notes"]
            site.resource_limits.save()

            yield ("after_state", str(site.resource_limits))

        wrapper.add_action("Updating Docker service", actions.update_docker_service)


@shared_task
def regen_site_secrets_task(operation_id: int) -> None:
    scope: Dict[str, Any] = {}

    site = Site.objects.get(operation__id=operation_id)

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        if site.database is not None:

            @wrapper.add_action("Regenerating database password")
            def regen_database_password(  # pylint: disable=unused-argument
                site: Site, scope: Dict[str, Any],
            ) -> Iterator[Union[Tuple[str, str], str]]:
                yield "Updating password in database model"

                assert site.database is not None

                site.database.password = gen_database_password()
                site.database.save()

                yield "Updating real password"

                database_utils.update_password(site.database)

        wrapper.add_action("Updating Docker service", actions.update_docker_service)


@shared_task
def delete_database_task(operation_id: int) -> None:
    site = Site.objects.get(operation__id=operation_id)
    if site.database is None:
        site.operation.delete()
        return

    scope: Dict[str, Any] = {}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        @wrapper.add_action("Deleting real database")
        def delete_real_database(  # pylint: disable=unused-argument
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield "Deleting real database"

            assert site.database is not None

            database_utils.delete_database(site.database)

        @wrapper.add_action("Deleting database object")
        def delete_database_object(  # pylint: disable=unused-argument
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield "Deleting database object in model"

            assert site.database is not None

            site.database.delete()

        wrapper.add_action("Updating Docker service", actions.update_docker_service)


@shared_task
def restart_service_task(operation_id: int) -> None:
    scope: Dict[str, Any] = {}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        wrapper.add_action("Restarting Docker service", actions.restart_docker_service)


@shared_task
def update_image_task(
    operation_id: int, base_image_name: str, write_run_sh_file: bool, package_names: List[str],
) -> None:
    scope: Dict[str, Any] = {
        "base_image_name": base_image_name,
        "write_run_sh_file": write_run_sh_file,
        "package_names": package_names,
    }

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        @wrapper.add_action("Updating site image object")
        def update_image_object(  # pylint: disable=unused-argument
            site: Site, scope: Dict[str, Any],
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield "Retrieving parent DockerImage"

            parent_image = DockerImage.objects.get(name=scope["base_image_name"])

            if not site.docker_image.is_custom:
                yield "Creating new DockerImage object for site"

                site.docker_image = DockerImage.objects.create(
                    # Basic attributes
                    name="site_{:04d}".format(site.id),
                    is_custom=True,
                    parent=parent_image,
                    # Just setting these for completeness; they
                    # all have sane defaults
                    is_user_visible=False,
                    friendly_name=None,
                    description="",
                    run_script_template="",
                )

                site.save()
            else:
                yield "Updating site DockerImage"
                site.docker_image.parent = parent_image
                site.docker_image.save()

            yield "Pruning image package list"
            site.docker_image.extra_packages.exclude(name__in=scope["package_names"]).delete()

            yield "Creating image package objects"
            for name in scope["package_names"]:
                DockerImageExtraPackage.objects.get_or_create(image=site.docker_image, name=name)

            yield "Models updated"

        wrapper.add_action("Building Docker image", actions.build_docker_image)

        if scope["write_run_sh_file"]:

            @wrapper.add_action("Writing run.sh")
            def do_write_run_sh_file(  # pylint: disable=unused-argument
                site: Site, scope: Dict[str, Any],
            ) -> Iterator[Union[Tuple[str, str], str]]:
                appserver = random.choice(scope["pingable_appservers"])

                if (
                    site.docker_image.parent is not None
                    and site.docker_image.parent.run_script_template
                ):
                    yield "Connecting to appserver {} to restart Docker service".format(appserver)
                    appserver_open_http_request(
                        appserver,
                        "/sites/{}/files/write".format(site.id),
                        params={"path": "run.sh", "mode": "0755"},
                        method="POST",
                        data=site.docker_image.parent.run_script_template.encode().rstrip() + b"\n",
                    )

                    yield "Successfully wrote run.sh"
                else:
                    yield "Skipping -- no run.sh template"

        wrapper.add_action("Updating Docker service", actions.update_docker_service)

        wrapper.add_action("Restarting Docker service", actions.restart_docker_service)


@shared_task
def create_site_task(operation_id: int) -> None:
    scope: Dict[str, Any] = {}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        wrapper.add_action("Creating Docker service", actions.update_docker_service)

        wrapper.add_action(
            "Updating appserver configuration", actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action(
                "Updating balancer configuration", actions.update_balancer_nginx_config
            )
