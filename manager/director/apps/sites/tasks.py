# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
# pylint: disable=unused-variable

from typing import Any, Dict, Iterator, Tuple, Union

from celery import shared_task

from django.conf import settings

from . import actions
from .helpers import auto_run_operation_wrapper
from .models import Site


@shared_task
def rename_site_task(operation_id: int, new_name: str):
    scope: Dict[str, Any] = {"new_name": new_name}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:

        @wrapper.add_action("Changing site name in database")
        def change_site_name(
            site: Site, scope: Dict[str, Any]
        ) -> Iterator[Union[Tuple[str, str], str]]:
            yield ("before_state", site.name)

            site.name = scope["new_name"]
            site.save(update_fields=["name"])

            yield ("after_state", site.name)

        wrapper.add_action("Updating appserver configuration")(
            actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action("Updating balancer configuration")(
                actions.update_balancer_nginx_config
            )


@shared_task
def create_site_task(operation_id: int):
    scope: Dict[str, Any] = {}

    with auto_run_operation_wrapper(operation_id, scope) as wrapper:
        wrapper.add_action("Selecting a port")(actions.select_site_port)

        wrapper.add_action("Creating Docker container")(
            actions.create_docker_container
        )

        wrapper.add_action("Updating appserver configuration")(
            actions.update_appserver_nginx_config
        )

        if not settings.DEBUG:
            wrapper.add_action("Updating balancer configuration")(
                actions.update_balancer_nginx_config
            )
