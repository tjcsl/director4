# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors
# pylint: disable=unused-variable

from typing import Any, Dict

from celery import shared_task

from .helpers import auto_run_operation_wrapper
from .models import Site


@shared_task
def rename_site_task(operation_id: int, new_name: str):
    with auto_run_operation_wrapper(operation_id, {"new_name": new_name}) as wrapper:

        @wrapper.add_action("Changing site name in database")
        def change_site_name(site: Site, scope: Dict[str, Any]) -> Dict[str, str]:
            result = {
                "before_state": site.name,
                "after_state": scope["new_name"],
            }
            site.name = scope["new_name"]
            site.save(update_fields=["name"])
            return result
