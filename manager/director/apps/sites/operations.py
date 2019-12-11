# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from .models import Operation, Site
from .tasks import rename_site_task


def rename_site(site: Site, new_name: str) -> None:
    operation = Operation.objects.create(site=site, type="rename_site")
    rename_site_task.delay(operation.id, new_name)
