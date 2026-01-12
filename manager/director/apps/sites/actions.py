# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
import random
from typing import Any, AsyncGenerator, Dict, Iterator, Tuple, Union

from django.conf import settings

from ...utils.appserver import (
    AppserverProtocolError,
    AppserverRequestError,
    appserver_open_http_request,
    appserver_open_websocket,
    iter_pingable_appservers,
)
from ...utils.balancer import balancer_open_http_request, iter_pingable_balancers
from ...utils.secret_generator import gen_database_password
from .models import Domain, Site


def find_pingable_appservers(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging appservers"
    pingable_appservers = list(iter_pingable_appservers())
    yield "Pingable appservers: {}".format(pingable_appservers)

    scope["pingable_appservers"] = pingable_appservers


def retry_appserver_request(
    description: str,
    request_fn: Any,
    *,
    attempts: int = 10,
    delay: float = 10.0,
) -> Iterator[Union[Tuple[str, str], str]]:
    for attempt in range(1, attempts + 1):
        try:
            return request_fn()
        except AppserverRequestError as ex:
            if attempt == attempts:
                yield "{} failed: {}".format(description, ex)
                raise

            continue


def update_appserver_nginx_config(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    try:
        yield from retry_appserver_request(
            "Connecting to appserver {} to update Nginx config".format(appserver),
            lambda: appserver_open_http_request(
                appserver,
                "/sites/{}/update-nginx".format(site.id),
                method="POST",
                data={"data": json.dumps(site.serialize_for_appserver())},
                timeout=120,
            ),
        )
    except AppserverRequestError:
        # If an error occurs, disable the Nginx config
        yield "Error updating Nginx config"

        yield "Disabling site Nginx config"
        yield from retry_appserver_request(
            "Connecting to appserver {} to disable Nginx config".format(appserver),
            lambda: appserver_open_http_request(
                appserver,
                "/sites/{}/disable-nginx".format(site.id),
                method="POST",
                timeout=120,
            ),
        )

        yield "Re-raising exception"
        raise
    else:
        # Success; try to reload
        yield "Successfully updated Nginx config"

        yield "Reloading Nginx config on all appservers"
        try:
            for i in scope["pingable_appservers"]:
                yield from retry_appserver_request(
                    "Reloading Nginx config on appserver {}".format(i),
                    lambda appserver=i: appserver_open_http_request(
                        appserver,
                        "/sites/reload-nginx",
                        method="POST",
                        timeout=120,
                    ),
                )
        except AppserverRequestError:
            # Error reloading; disable config
            # We're probably fine not reloading Nginx
            yield "Error reloading Nginx config"

            yield "Disabling site Nginx config"
            yield from retry_appserver_request(
                "Connecting to appserver {} to disable Nginx config".format(appserver),
                lambda: appserver_open_http_request(
                    appserver,
                    "/sites/{}/disable-nginx".format(site.id),
                    method="POST",
                    timeout=120,
                ),
            )

            yield "Re-raising exception"
            raise
        else:
            # Everything succeeded!
            yield "Successfully reloaded configuration"


def remove_appserver_nginx_config(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])
    yield from retry_appserver_request(
        "Connecting to appserver {} to remove Nginx config".format(appserver),
        lambda: appserver_open_http_request(
            appserver,
            "/sites/{}/remove-nginx".format(site.id),
            method="POST",
            timeout=120,
        ),
    )

    yield "Reloading Nginx config on all appservers"
    for i in scope["pingable_appservers"]:
        yield from retry_appserver_request(
            "Reloading Nginx config on appserver {}".format(i),
            lambda appserver=i: appserver_open_http_request(
                appserver,
                "/sites/reload-nginx",
                method="POST",
                timeout=120,
            ),
        )

    yield "Done"


def update_docker_service(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    if site.availability == "disabled":
        yield from remove_docker_service(site, scope)
        return

    appserver = random.choice(scope["pingable_appservers"])

    yield from retry_appserver_request(
        "Connecting to appserver {} to create/update Docker service".format(appserver),
        lambda: appserver_open_http_request(
            appserver,
            "/sites/{}/update-docker-service".format(site.id),
            method="POST",
            data={"data": json.dumps(site.serialize_for_appserver())},
        ),
    )

    yield "Created/updated Docker service"


def restart_docker_service(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    if site.availability == "disabled":
        yield "Site disabled; skipping"
        return

    appserver = random.choice(scope["pingable_appservers"])

    yield from retry_appserver_request(
        "Connecting to appserver {} to restart Docker service".format(appserver),
        lambda: appserver_open_http_request(
            appserver,
            "/sites/{}/restart-docker-service".format(site.id),
            method="POST",
        ),
    )

    yield "Restarted Docker service"


def remove_docker_service(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    yield from retry_appserver_request(
        "Connecting to appserver {} to remove Docker service".format(appserver),
        lambda: appserver_open_http_request(
            appserver,
            "/sites/{}/remove-docker-service".format(site.id),
            method="POST",
        ),
    )

    yield "Removed Docker service"


def build_docker_image(site: Site, scope: Dict[str, Any]) -> Iterator[Union[Tuple[str, str], str]]:
    if not site.docker_image.is_custom:
        yield "Site does not have a custom Docker image; skipping"
        return

    appserver = hash(str(site.id) + site.name) % settings.DIRECTOR_NUM_APPSERVERS

    if appserver not in scope["pingable_appservers"]:
        appserver = random.choice(scope["pingable_appservers"])

    executor = build_docker_image_async(appserver, site.docker_image.serialize_for_appserver())

    # Async generators are hard in synchronous code
    while True:
        try:
            item = asyncio.get_event_loop().run_until_complete(executor.__anext__())
        except StopAsyncIteration:
            break
        else:
            yield item

    yield "Built Docker image"


async def build_docker_image_async(
    appserver_num: int,
    data: Dict[str, Any],
) -> AsyncGenerator[Union[Tuple[str, str], str], None]:
    yield "Connecting to appserver {} to build Docker image".format(appserver_num)
    websock = await asyncio.wait_for(
        appserver_open_websocket(appserver_num, "/ws/sites/build-docker-image"),
        timeout=10,
    )

    await websock.send(json.dumps(data))

    result = json.loads(await websock.recv())
    yield "Result: {}".format(result)

    if not result["successful"]:
        raise Exception(result["msg"])


def remove_docker_image(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    if not site.docker_image.is_custom:
        yield "Site does not have a custom Docker image; skipping"
        return

    for i in range(settings.DIRECTOR_NUM_APPSERVERS):
        yield "Removing Docker image on appserver {}".format(i)

        yield from retry_appserver_request(
            "Connecting to appserver {} to remove Docker image".format(i),
            lambda appserver=i: appserver_open_http_request(
                appserver,
                "/sites/remove-docker-image",
                params={"name": site.docker_image.name},
                method="POST",
            ),
        )

        yield "Removing Docker image from registry on appserver {}".format(i)

        yield from retry_appserver_request(
            "Connecting to appserver {} to remove registry image".format(i),
            lambda appserver=i: appserver_open_http_request(
                appserver,
                "/sites/remove-registry-image",
                params={"name": site.docker_image.name},
                method="POST",
            ),
        )


def ensure_site_directories_exist(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    yield from retry_appserver_request(
        "Connecting to appserver {} to ensure site directories exist".format(appserver),
        lambda: appserver_open_http_request(
            appserver,
            "/sites/{}/ensure-directories-exist".format(site.id),
            method="POST",
        ),
    )


async def remove_all_site_files_dangerous_async(appserver_num: int, site_id: int) -> None:
    websock = await asyncio.wait_for(
        appserver_open_websocket(
            appserver_num,
            "/ws/sites/{}/files/remove-all-site-files-dangerous".format(site_id),
        ),
        timeout=10,
    )

    result = json.loads(await websock.recv())

    if not result["successful"]:
        raise Exception(result["msg"])


def remove_all_site_files_dangerous(
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    appserver = random.choice(scope["pingable_appservers"])

    yield "Connecting to appserver {} to remove site files".format(appserver)

    asyncio.get_event_loop().run_until_complete(
        remove_all_site_files_dangerous_async(appserver, site.id)
    )

    yield "Removed site files"


def update_balancer_nginx_config(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging balancers"
    pingable_balancers = list(iter_pingable_balancers())
    yield "Pingable balancers: {}".format(pingable_balancers)

    for i in pingable_balancers:
        yield "Updating balancer {}".format(i)
        balancer_open_http_request(
            i,
            "/sites/{}/update-nginx".format(site.id),
            data={"data": json.dumps(site.serialize_for_balancer())},
            method="POST",
        )
        yield "Updated balancer {}".format(i)


def remove_balancer_nginx_config(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    yield "Pinging balancers"
    pingable_balancers = list(iter_pingable_balancers())
    yield "Pingable balancers: {}".format(pingable_balancers)

    for i in pingable_balancers:
        yield "Removing Nginx config on balancer {}".format(i)
        balancer_open_http_request(i, "/sites/{}/remove-nginx".format(site.id), method="POST")
        yield "Removed Nginx config on balancer {}".format(i)


def update_balancer_certbot(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    if settings.DIRECTOR_NUM_BALANCERS:
        yield "Setting up certbot for site"
        balancer_open_http_request(
            0,
            "/sites/{}/certbot-setup".format(site.id),
            data={"data": json.dumps(site.serialize_for_balancer())},
            method="POST",
        )

        yield "Removing old domains"
        balancer_open_http_request(
            0,
            "/sites/certbot-remove-old-domains",
            data={
                "domains": json.dumps(
                    list(Domain.objects.exclude(status="active").values_list("domain", flat=True))
                ),
            },
            method="POST",
        )


def delete_site_database_and_object(  # pylint: disable=unused-argument
    site: Site, scope: Dict[str, Any]
) -> Iterator[Union[Tuple[str, str], str]]:
    assert site.database is not None

    appserver_num = random.choice(scope["pingable_appservers"])

    yield "Connecting to appserver {} to delete real database".format(appserver_num)
    yield from retry_appserver_request(
        "Connecting to appserver {} to delete real database".format(appserver_num),
        lambda: appserver_open_http_request(
            appserver_num,
            "/sites/databases/delete",
            method="POST",
            data={"data": json.dumps(site.database.serialize_for_appserver())},
            timeout=90,
        ),
    )

    yield "Deleting database object in model"
    site.database.delete()


def create_real_site_database(site: Site, scope: Dict[str, Any]):  # pylint: disable=unused-argument
    assert site.database is not None

    appserver_num = random.choice(scope["pingable_appservers"])

    yield from retry_appserver_request(
        "Connecting to appserver {} to create real site database".format(appserver_num),
        lambda: appserver_open_http_request(
            appserver_num,
            "/sites/databases/create",
            method="POST",
            data={"data": json.dumps(site.database.serialize_for_appserver())},
            timeout=90,
        ),
    )


def regen_database_password(site: Site, scope: Dict[str, Any]):  # pylint: disable=unused-argument
    yield "Updating password in database model"

    assert site.database is not None

    site.database.password = gen_database_password()
    site.database.save()

    appserver_num = random.choice(scope["pingable_appservers"])

    yield from retry_appserver_request(
        "Connecting to appserver {} to update real password".format(appserver_num),
        lambda: appserver_open_http_request(
            appserver_num,
            "/sites/databases/create",
            method="POST",
            data={"data": json.dumps(site.database.serialize_for_appserver())},
            timeout=90,
        ),
    )
