# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models  # pylint: disable=unused-import # noqa
from django.db.models import Q
from django.utils import timezone

from ...utils import split_domain
from ...utils.site_names import is_site_name_allowed


class SiteQuerySet(models.query.QuerySet):
    def filter_for_user(self, user) -> "models.query.QuerySet[Site]":
        if user.is_superuser:
            return self.all()
        else:
            return self.filter(users=user)


class Site(models.Model):
    SITE_TYPES = [
        ("static", "Static"),
        ("dynamic", "Dynamic"),
    ]

    PURPOSES = [
        ("legacy", "Legacy"),
        ("user", "User"),
        ("project", "Project"),
        ("activity", "Activity"),
        ("other", "Other"),
    ]

    objects: Any = SiteQuerySet.as_manager()

    # Website name
    name = models.CharField(
        max_length=32,
        unique=True,
        # Don't replace these classes with "\w". That allows Unicode characters. We just want ASCII.
        validators=[
            MinLengthValidator(2),
            RegexValidator(
                regex=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$",
                message="Site names must consist of lowercase letters, numbers, and dashes. Names "
                "cannot start with a number, and dashes must go between two non-dash characters.",
            ),
        ],
    )
    # Some kind of description.
    description = models.TextField(blank=True)

    # What runs on the site
    type = models.CharField(max_length=16, choices=SITE_TYPES)
    # What the site is created for
    purpose = models.CharField(max_length=16, choices=PURPOSES)
    # The Docker image running on here
    docker_image = models.ForeignKey("DockerImage", null=False, on_delete=models.PROTECT)
    # Users who have access to this site
    users = models.ManyToManyField(get_user_model(), blank=True)

    # The site database
    database = models.OneToOneField(
        "Database", null=True, blank=True, on_delete=models.SET_NULL, related_name="site"
    )

    # Tell Pylint about the implicit related field
    resource_limits: "SiteResourceLimits"

    @property
    def site_path(self) -> str:
        return "/web/site-{}".format(self.id)

    def list_urls(self) -> List[str]:
        urls = [
            ("https://" + domain) for domain in self.domain_set.values_list("domain", flat=True)
        ]

        urls.append(self.sites_url)

        return urls

    @property
    def sites_url(self) -> str:
        return settings.SITE_URL_FORMATS.get(self.purpose, settings.SITE_URL_FORMATS[None]).format(
            self.name
        )

    @property
    def main_url(self) -> str:
        # Use the first custom domain if one exists
        domain = self.domain_set.values_list("domain", flat=True).first()
        if domain is not None:
            return "https://{}".format(domain)

        # Then the "sites" URL
        return self.sites_url

    def serialize_for_appserver(self) -> Dict[str, Any]:
        main_url = self.main_url
        if main_url:
            main_url = main_url.rstrip("/")

        return {
            "name": self.name,
            "no_redirect_domains": list({split_domain(url) for url in self.list_urls()}),
            "primary_url_base": main_url,
            "database_url": (self.database.db_url if self.database is not None else None),
            "docker_image": self.docker_image.serialize_for_appserver(),
            "resource_limits": self.serialize_resource_limits(),
        }

    def serialize_for_balancer(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "custom_domains": list(
                self.domain_set.filter(status="active").values_list("domain", flat=True)
            ),
        }

    def serialize_resource_limits(self) -> Dict[str, Any]:
        limits = {
            "cpus": settings.DIRECTOR_RESOURCES_DEFAULT_CPUS,
            "mem_limit": settings.DIRECTOR_RESOURCES_DEFAULT_MEMORY_LIMIT,
        }

        try:
            resource_limits = self.resource_limits
        except SiteResourceLimits.DoesNotExist:
            return limits

        for name in ["cpus", "mem_limit"]:
            value = getattr(resource_limits, name)

            # Only use if the new value if a) it's not None or "" and b) either it's not a number or
            # it's <= 0
            if (
                value is not None
                and value != ""
                and (not isinstance(value, (int, float)) or value > 0)
            ):
                limits[name] = value

        return limits

    @property
    def has_operation(self) -> bool:
        return Operation.objects.filter(site__id=self.id).exists()

    @property
    def has_database(self) -> bool:
        return Database.objects.filter(site__id=self.id).exists()

    @property
    def channels_group_name(self) -> str:
        return "site-{}".format(self.id)

    def clean(self) -> None:
        super().clean()

        if not is_site_name_allowed(self.name):
            raise ValidationError("This site name is not allowed.")

    def save(self, *args: Any, **kwargs: Any) -> None:  # pylint: disable=arguments-differ
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return "<Site: " + str(self) + ">"


class SiteResourceLimitsQuerySet(models.query.QuerySet):
    def filter_has_custom_limits(self) -> "models.query.QuerySet[SiteResourceLimits]":
        """Filters this QuerySet to only the SiteResourceLimits objects with values that
        will actually lead to at least one non-default limit being used.

        This is necessary because a the simple existence of SiteResourceLimits object does
        not necessarily mean that site has custom limits set.

        """
        return self.filter(Q(cpus__isnull=False) | Q(cpus__gt=0) | ~Q(mem_limit=""))


class SiteResourceLimits(models.Model):
    objects = SiteResourceLimitsQuerySet.as_manager()

    site = models.OneToOneField(
        Site, null=False, blank=False, on_delete=models.CASCADE, related_name="resource_limits",
    )

    # Fractions of a CPU
    cpus = models.FloatField(
        null=True,
        blank=True,
        default=None,
        # Must be between 0 and 3
        validators=[MinValueValidator(0), MaxValueValidator(3)],
    )

    # Memory limit
    mem_limit = models.CharField(
        null=False,
        blank=True,
        default="",
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(\d+(\s*[KMG]i?B)?)?$",
                message="Must be either 1) blank for the default limit or 2) a number followed by "
                "one of the suffixes KiB, MiB, or GiB (powers of 1024) or KB, MB, GB (powers of "
                "1000).",
            ),
        ],
    )

    # Administrative notes about why the site has been allocated extra resources
    notes = models.TextField(null=False, blank=True, default="")

    # IMPORTANT: Do not add additional fields without adding the appropriate filters to
    # SiteResourceLimitsQuerySet.filter_has_custom_limits() above!!!

    def stringify_limits(self) -> str:
        return "cpus={}, mem_limit={}".format(self.cpus, self.mem_limit or None)

    def __str__(self) -> str:
        return "Site {}: {}".format(self.site.name, self.stringify_limits())

    def __repr__(self):
        return "<SiteResourceLimits: " + str(self) + ">"


class DockerImageQuerySet(models.query.QuerySet):
    def get_default_image(self) -> "DockerImage":
        return self.get_or_create(
            name=settings.DIRECTOR_DEFAULT_DOCKER_IMAGE,
            defaults={
                "friendly_name": settings.DIRECTOR_DEFAULT_DOCKER_IMAGE_FRIENDLY_NAME,
                "is_custom": False,
                "is_user_visible": False,
                "parent": None,
                "install_command_prefix": (
                    settings.DIRECTOR_DEFAULT_DOCKER_IMAGE_INSTALL_COMMAND_PREFIX
                ),
            },
        )[0]

    def filter_user_visible(self) -> "models.query.QuerySet[DockerImage]":
        return self.filter(is_user_visible=True, is_custom=False, friendly_name__isnull=False)


def _docker_image_get_default_image() -> "DockerImage":
    return DockerImage.objects.get_default_image()  # type: ignore


class DockerImage(models.Model):
    objects = DockerImageQuerySet.as_manager()

    # Examples: legacy_director_dynamic, site_1
    # For non-custom images (parent images), these should always be ":latest" images.
    # Weird things will happen if they aren't.
    name = models.CharField(max_length=32, blank=False, null=False, unique=True)

    # Will be shown to the user.
    friendly_name = models.CharField(
        max_length=32, blank=True, null=True, unique=True, default=None,
    )

    # A general description of what is in the image, what it's useful for, etc.
    # The user will see this when they select an image.
    description = models.TextField(blank=True, null=False, default="")

    # True if created by a user, False if created by a Director admin
    is_custom = models.BooleanField(null=False)

    # If this is set to True, users will be allowed to select this image on the image
    # selection form.
    # If is_custom is False or friendly_name is null, this is implicitly False.
    is_user_visible = models.BooleanField(null=False, default=False)

    # Parent image, for custom images
    parent = models.ForeignKey(
        "DockerImage",
        null=True,
        blank=True,
        unique=False,
        on_delete=models.SET(_docker_image_get_default_image),
        related_name="children",
    )

    # This will be run with sh -c '<cmd> <pkgs>' where <cmd> is this command
    # and <pkgs> is a space-separated list of packages.
    install_command_prefix = models.TextField(blank=True, null=False, default="")

    # The user will have the option to copy this into their site's run.sh
    # when they select a Docker image.
    run_script_template = models.TextField(blank=True, null=False, default="")

    def get_full_install_command(self) -> Optional[str]:
        """Get the full command to install all of this site's packages, or None
        if it has no packages to install."""

        if self.parent is not None:
            install_command_prefix = self.parent.install_command_prefix
            if not install_command_prefix:
                return None
        else:
            return None

        package_names = self.extra_packages.values_list("name", flat=True)
        if package_names.exists():
            return install_command_prefix + " " + " ".join(package_names)
        else:
            return None

    def serialize_for_appserver(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_custom": self.is_custom,
            "parent_name": (self.parent.name if self.parent is not None else None),
            "full_install_command": self.get_full_install_command(),
        }

    def __str__(self) -> str:
        res = self.name

        labels = []

        if self.is_custom:
            labels.append("custom")
        if self.parent is not None:
            labels.append("from " + self.parent.name)

        if labels:
            res += " ({})".format(", ".join(labels))

        return res

    def __repr__(self) -> str:
        return "<DockerImage: " + str(self) + ">"


class DockerImageExtraPackage(models.Model):
    image = models.ForeignKey(
        "DockerImage", null=False, on_delete=models.CASCADE, related_name="extra_packages"
    )
    # Package name
    name = models.CharField(max_length=60, blank=False, null=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["image", "name"], name="unique_image_package")
        ]


class Domain(models.Model):
    """Represents a custom (non-`sites.tjhsst.edu`) domain.

    `sites.tjhsst.edu` domains MUST be set up by creating a site with that name.

    Note: It must be ensured that *.tjhsst.edu domains can only be set up by Director admins.

    """

    STATUSES = [
        # Enabled (most domains)
        ("active", "Active"),
        # Disabled (respected in generation of configuration, but currently no provisions for
        # setting domains to inactive)
        ("inactive", "Inactive"),
        # Reserved domains we don't want people to use for legal/policy reasons (these should always
        # have site=None)
        ("blocked", "Blocked"),
    ]

    # Should ONLY be None for blocked domains
    site = models.ForeignKey(Site, null=True, on_delete=models.PROTECT)

    domain = models.CharField(
        max_length=255,
        validators=[
            RegexValidator(
                regex=r"^(?!(.*\.)?sites\.tjhsst\.edu$)[0-9a-zA-Z_\- .]+$",
                message="You can only have one sites.tjhsst.edu domain, and it must match the name "
                "of your site.",
            )
        ],
    )

    created_time = models.DateTimeField(auto_now_add=True, null=False)
    creating_user = models.ForeignKey(get_user_model(), null=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=8, choices=STATUSES, default="active")


class DatabaseHost(models.Model):
    # These should be capable of being put in a database URL
    # Hence "postgres", not "postgresql"
    DBMS_TYPES = [
        ("postgres", "PostgreSQL"),
        ("mysql", "MySQL"),
    ]

    hostname = models.CharField(max_length=255)
    port = models.PositiveIntegerField()

    dbms = models.CharField(max_length=16, choices=DBMS_TYPES)

    admin_username = models.CharField(max_length=255, null=False, blank=False)
    admin_password = models.CharField(max_length=255, null=False, blank=False)

    def __str__(self) -> str:
        return "{}:{} ({})".format(self.hostname, self.port, self.get_dbms_display())


class Database(models.Model):
    host = models.ForeignKey(DatabaseHost, on_delete=models.CASCADE)
    password = models.CharField(max_length=255, null=False, blank=False)

    @property
    def db_name(self) -> str:
        return "site_{}".format(self.site.id)  # pylint: disable=no-member

    @property
    def username(self) -> str:
        return "site_{}".format(self.site.id)  # pylint: disable=no-member

    @property
    def db_host(self) -> str:
        return self.host.hostname

    @property
    def db_port(self) -> int:
        return self.host.port

    @property
    def db_type(self) -> str:
        return self.host.dbms

    @property
    def db_url(self) -> str:
        return "{}://{}:{}@{}:{}/{}".format(
            self.db_type, self.username, self.password, self.db_host, self.db_port, self.db_name
        )


class Operation(models.Model):
    # WARNING: Make sure to update locks_database and locks_container if you edit this list!
    OPERATION_TYPES = [
        # Create a site (no database)
        ("create_site", "Creating site"),
        # Rename the site. Changes the site name and the default domain name.
        ("rename_site", "Renaming site",),
        # Change the site name and domain names
        ("edit_site_names", "Changing site name/domains"),
        # Change the site type (example: static -> dynamic)
        ("change_site_type", "Changing site type"),
        # Something was changed that requires the Nginx config to be regenerated and saved, but no
        # other changes.
        ("regen_nginx_config", "Regenerating Nginx configuration"),
        # Create a database for the site
        ("create_site_database", "Creating site database"),
        # Create a database for the site
        ("delete_site_database", "Deleting site database"),
        # Regenerate the database password.
        ("regen_site_secrets", "Regenerating site secrets"),
        # Updating the site's resource limits
        ("update_resource_limits", "Updating site resource limits"),
        # Updating something about the site's Docker image
        ("update_docker_image", "Updating site Docker image"),
        # Delete a site, its files, its database, its Docker image, etc.
        ("delete_site", "Deleting site"),
        # Restart a site's process
        ("restart_site", "Restarting site"),
    ]

    site = models.OneToOneField(Site, null=False, on_delete=models.PROTECT)
    type = models.CharField(max_length=24, choices=OPERATION_TYPES)
    created_time = models.DateTimeField(auto_now_add=True, null=False)
    started_time = models.DateTimeField(null=True)

    @property
    def has_started(self) -> bool:
        return self.started_time is not None

    def start_operation(self) -> None:
        self.started_time = timezone.localtime()
        self.save(update_fields=["started_time"])

    @property
    def locks_database(self) -> bool:
        """Returns whether database access should be blocked while this operation completes."""
        return self.type in {"create_site_database", "regen_database_password", "delete_site"}

    @property
    def locks_container(self) -> bool:
        """Returns whether the Docker container should be blocked from launching while this
        operation completes."""
        # If this operation locks the database and this site has a database, then it also locks the
        # container.
        if self.locks_database and self.site.database is not None:
            return True

        # These do NOT lock the container (that list is shorter the the list of ones that do)
        return self.type not in {
            "rename_site",
            "change_site_domains",
            "regen_nginx_config",
            "regen_database_password",
        }

    def list_actions_in_order(self) -> "models.QuerySet[Action]":
        return self.action_set.order_by("id")


class Action(models.Model):
    operation = models.ForeignKey(Operation, null=False, on_delete=models.PROTECT)

    # Example: "update_nginx_config"
    slug = models.CharField(
        max_length=40,
        null=False,
        blank=False,
        validators=[MinLengthValidator(4), RegexValidator(regex=r"^[a-z]+(_[a-z]+)+$")],
    )
    # May be displayed to the user for progress updates. Example: "Updating Nginx config"
    name = models.CharField(max_length=80, null=False, blank=False)
    # Time this action was started. Only None if it hasn't been started yet.
    started_time = models.DateTimeField(null=True)

    # These are a little tricker.
    # The idea is that these will be some kind of string representing the "before" and "after"
    # states of whatever is being modified. An empty string denotes N/A.
    # For example, if a database named "site_188" is being created, before_state is "" and
    # after_state is "site_188"
    before_state = models.CharField(max_length=255, null=False, blank=True)
    after_state = models.CharField(max_length=255, null=False, blank=True)

    # This indicates a command that is roughly equivalent to the task this Action performs.
    # Example:
    # An empty string indicates N/A (for things like connecting to the appserver or asking the
    # appserver to generate a config file)
    equivalent_command = models.CharField(max_length=200, null=False, blank=True)
    # None=Not finished, True=Successful, False=Failed
    result = models.BooleanField(null=True, default=None)
    # Some kind of message describing the actions taken or anything that failed in further detail.
    # *** ONLY VISIBLE TO SUPERUSERS ***
    # For example, if there was a syntax error in the Nginx config, this should contain the output
    # of the command run to check the Nginx config.
    # Should always be set for failed actions. Optional, but encouraged, for successful actions.
    message = models.TextField(null=False, blank=True)

    @property
    def has_started(self) -> bool:
        return self.started_time is not None

    def start_action(self) -> None:
        self.started_time = timezone.localtime()
        self.save(update_fields=["started_time"])

    @property
    def finished(self) -> bool:
        return self.result is not None

    @property
    def succeeded(self) -> bool:
        return self.result is True

    @property
    def failed(self) -> bool:
        return self.result is False

    @property
    def result_msg(self) -> str:
        if self.result:
            return "Success"
        elif self.result is None:
            return "Not finished"
        else:
            return "Failed"
