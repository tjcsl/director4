# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import List

from .models import DatabaseHost, Operation, Site
from .tasks import (
    create_database_task,
    create_site_task,
    delete_database_task,
    edit_site_names_task,
    regen_nginx_config_task,
    regen_site_secrets_task,
    rename_site_task,
)


def rename_site(site: Site, new_name: str) -> None:
    operation = Operation.objects.create(site=site, type="rename_site")
    rename_site_task.delay(operation.id, new_name)


def regen_nginx_config(site: Site) -> None:
    operation = Operation.objects.create(site=site, type="regen_nginx_config")
    regen_nginx_config_task.delay(operation.id)


def create_database(site: Site, database_host: DatabaseHost) -> None:
    operation = Operation.objects.create(site=site, type="create_site_database")
    create_database_task.delay(operation.id, database_host.id)


def delete_database(site: Site) -> None:
    operation = Operation.objects.create(site=site, type="delete_site_database")
    delete_database_task.delay(operation.id)


def regen_site_secrets(site: Site) -> None:
    operation = Operation.objects.create(site=site, type="regen_site_secrets")
    regen_site_secrets_task.delay(operation.id)


def edit_site_names(
    site: Site,
    *,
    new_name: str,
    sites_domain_enabled: bool,
    domains: List[str],
    request_username: str
) -> None:
    operation = Operation.objects.create(site=site, type="edit_site_names")
    edit_site_names_task.delay(
        operation.id,
        new_name=new_name,
        sites_domain_enabled=sites_domain_enabled,
        domains=domains,
        request_username=request_username,
    )


def create_site(site: Site) -> None:
    operation = Operation.objects.create(site=site, type="create_site")
    create_site_task.delay(operation.id)
