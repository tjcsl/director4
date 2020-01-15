# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
# pylint: disable=unused-variable

from typing import Any, Dict, Iterator, List, Tuple, Union

from celery import shared_task

from django.conf import settings
from django.contrib.auth import get_user_model

from . import actions
from .helpers import auto_run_operation_wrapper
from .models import Domain, Site


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
                except Domain.DoesNotExist:
                    Domain.objects.create(site=site, domain=domain_name, creating_user=request_user)
                else:
                    if domain_obj.site is not None and domain_obj.site.id != site.id:
                        yield "Domain {} belongs to another site; silently ignoring".format(
                            domain_name,
                        )
                    else:
                        yield "Domain {} already belongs to site {}".format(domain_name, site.id)

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
def create_site_task(operation_id: int):
    scope: Dict[str, Any] = {}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Pinging appservers", actions.find_pingable_appservers)

        wrapper.add_action("Selecting a port", actions.select_site_port)

        wrapper.add_action("Creating Docker container", actions.create_docker_container)

        wrapper.add_action(
            "Updating appserver configuration", actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action(
                "Updating balancer configuration", actions.update_balancer_nginx_config
            )
