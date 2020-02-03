# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
# pylint: disable=unused-variable

from typing import Any, Dict, Iterator, List, Tuple, Union

from celery import shared_task

from django.conf import settings
from django.contrib.auth import get_user_model

from ...utils import database as database_utils
from ...utils.secret_generator import gen_database_password
from . import actions
from .helpers import auto_run_operation_wrapper
from .models import Database, DatabaseHost, Domain, Site


@shared_task
def rename_site_task(operation_id: int, new_name: str):
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
    operation_id: int,
    *,
    new_name: str,
    sites_domain_enabled: bool,
    domains: List[str],
    request_username: str,
):
    scope: Dict[str, Any] = {
        "new_name": new_name,
        "sites_domain_enabled": sites_domain_enabled,
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

            site.sites_domain_enabled = scope["sites_domain_enabled"]
            site.save(update_fields=["sites_domain_enabled"])
            yield "Set site.sites_domain_enabled"

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
def regen_nginx_config_task(operation_id: int):
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
def create_database_task(operation_id: int, database_host_id: int):
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
def regen_site_secrets_task(operation_id: int):
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
def delete_database_task(operation_id: int):
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
def create_site_task(operation_id: int):
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
