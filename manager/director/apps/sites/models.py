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
    def listable_by_user(self, user) -> "models.query.QuerySet[Site]":
        """WARNING: Use editable_by_user() for permission checks instead, unless
        you immediately check site.can_be_edited_by(user) and handle accordingly.

        The purpose of this function is that if a site has been disabled, the users
        who have access to it should be able to see that it is still present (i.e.
        it doesn't "disappear"). However, all other permissions checks for
        viewing/editing information use `editable_by_user()`, which only allows access
        if the site is not disabled.

        """

        if user.is_superuser:
            return self.all()
        else:
            return self.filter(users=user)

    def editable_by_user(self, user) -> "models.query.QuerySet[Site]":
        query = self.listable_by_user(user)

        if not user.is_superuser:
            query = query.filter(availability__in=["enabled", "not-served"])

        return query


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

    AVAILABILITIES = [
        ("enabled", "Enabled (fully functional)"),
        ("not-served", "Not served publicly"),
        ("disabled", "Disabled (not served, only viewable/editable by admins)"),
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
                regex=r"^[a-z0-9]+(-[a-z0-9]+)*$",
                message="Site names must consist of lowercase letters, numbers, and dashes. Dashes "
                "must go between two non-dash characters.",
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

    availability = models.CharField(
        max_length=max(len(item[0]) for item in AVAILABILITIES),
        choices=AVAILABILITIES,
        default="enabled",
        help_text="Controls availability of the site (whether it is served publicly and whether it "
        "is editable)",
    )

    admin_comments = models.TextField(
        null=False,
        blank=True,
        help_text="Administrative comments. All users who have access to the site will always be "
        "able to see this, even if the site's 'availability' is 'disabled'.",
    )

    custom_nginx_config = models.TextField(
        null=False,
        blank=True,
        help_text="Custom rules to add to the Nginx config (in the location /) block",
    )

    # Tell Pylint about the implicit related field
    resource_limits: "SiteResourceLimits"

    def can_be_edited_by(self, user) -> bool:
        return user.is_authenticated and (
            user.is_superuser
            or (
                self.users.filter(id=user.id).exists()
                and self.availability in ["enabled", "not-served"]
            )
        )

    @property
    def is_being_served(self) -> bool:
        return self.availability == "enabled"

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
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "is_being_served": self.is_being_served,
            "no_redirect_domains": list({split_domain(url) for url in self.list_urls()}),
            "primary_url_base": main_url,
            "database_info": (
                {
                    "url": self.database.db_url,
                    "type": self.database.db_type,
                    "host": self.database.db_host,
                    "port": self.database.db_port,
                    "name": self.database.db_name,
                    "username": self.database.username,
                    "password": self.database.password,
                }
                if self.database is not None
                else None
            ),
            "docker_image": self.docker_image.serialize_for_appserver(),
            "resource_limits": self.serialize_resource_limits(),
            "custom_nginx_config": self.custom_nginx_config,
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
            "client_body_limit": str(settings.DIRECTOR_RESOURCES_DEFAULT_CLIENT_BODY_LIMIT),
        }

        try:
            resource_limits = self.resource_limits
        except SiteResourceLimits.DoesNotExist:
            return limits

        for name in ["cpus", "mem_limit", "client_body_limit"]:
            value = getattr(resource_limits, name)

            # Only use if the new value if a) it's not None or "" and b) either it's not a number or
            # it's > 0
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

    def get_operation(self) -> Optional["Operation"]:
        try:
            return self.operation  # pylint: disable=no-member
        except Operation.DoesNotExist:
            return None

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

    def save(self, *args: Any, **kwargs: Any) -> None:  # pylint: disable=signature-differs
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    def __repr__(self):
        return "<Site: " + str(self) + ">"


class SitePendingUser(models.Model):
    sites = models.ManyToManyField(Site, blank=False, related_name="pending_users")

    username = models.CharField(max_length=80, null=False, blank=False, unique=True)

    @classmethod
    def add_user_site(cls, username: str, site: Site) -> None:
        assert isinstance(username, str)
        pending_user = cls.objects.get_or_create(username=username)[0]
        pending_user.sites.add(site)

    def process_and_delete(self, user) -> None:
        assert user.username == self.username

        for site in self.sites.all():
            site.users.add(user)

        self.delete()


class SiteResourceLimitsQuerySet(models.query.QuerySet):
    def filter_has_custom_limits(self) -> "models.query.QuerySet[SiteResourceLimits]":
        """Filters this QuerySet to only the SiteResourceLimits objects with values that
        will actually lead to at least one non-default limit being used.

        This is necessary because a the simple existence of SiteResourceLimits object does
        not necessarily mean that site has custom limits set.

        """
        return self.filter(
            Q(cpus__isnull=False) | Q(cpus__gt=0) | ~Q(mem_limit="") | ~Q(client_body_limit="")
        )


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

    # Client body (aka file upload) size limit
    client_body_limit = models.CharField(
        null=False,
        blank=True,
        default="",
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(\d+[kKmM]?)?$",
                message="Must be either 1) blank for the default limit or 2) a number, optionally "
                "followed by one of the suffixes k/K or m/M.",
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
    name = models.CharField(
        max_length=75,
        blank=False,
        null=False,
        unique=True,
        help_text='These should always be ":latest" or equivalent images. Weird things will '
        "happen if they aren't. Warning: You cannot edit this field once the image has been "
        "created. Allowing that would break a fundamental assumption of the image handling code.",
    )

    friendly_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        default=None,
        help_text="Will be shown to the user.",
    )

    logo_url = models.URLField(max_length=300, blank=True, null=False, default="")

    description = models.TextField(
        blank=True,
        null=False,
        default="",
        help_text="A general description of what is in the image, what it's useful for, etc. The "
        "user will see this when they select an image.",
    )

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

    setup_commands = models.ManyToManyField(
        "DockerImageSetupCommand", blank=True, related_name="docker_images"
    )

    base_install_command = models.TextField(
        blank=True,
        null=False,
        default="",
        help_text="A command to run after the setup commands, but before custom packages are "
        "installed. This should be used to install basic dependencies specific to this image; for "
        "something broader (OS/language-specific), use a setup command instead. Be careful about "
        "syntax errors; everything is '&&'-ed together.",
    )

    install_command_prefix = models.TextField(
        blank=True,
        null=False,
        default="",
        help_text="This is run with '<cmd> <pkgs>' where <cmd> is this command and <pkgs> is a "
        "space-separated list of packages.",
    )

    run_script_template = models.TextField(
        blank=True,
        null=False,
        default="",
        help_text="The user will have the option to copy this into their site's run.sh when they "
        "select a Docker image.",
    )

    def get_setup_command(self) -> Optional[str]:
        """Get the command to perform all of the setup required by this image, or None
        if there is nothing to do.

        This is designed to be run on the parent image of a custom image.

        """

        command_parts = list(self.setup_commands.values_list("command", flat=True))

        if self.base_install_command:
            command_parts.append(self.base_install_command)

        return " && ".join(command_parts) if command_parts else None

    def get_install_command(self) -> Optional[str]:
        """Get the command to install all of this site's packages, or None if there
        is nothing to do.

        This is designed to be run on a custom image.

        """

        if self.parent is not None and self.parent.install_command_prefix:
            package_names = self.extra_packages.values_list("name", flat=True)
            if package_names.exists():
                return self.parent.install_command_prefix + " " + " ".join(package_names)

        return None

    def serialize_for_appserver(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_custom": self.is_custom,
            "parent_name": (self.parent.name if self.parent is not None else None),
            "parent_setup_command": (
                self.parent.get_setup_command() if self.parent is not None else None
            ),
            "install_command": self.get_install_command(),
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


class DockerImageSetupCommandManager(models.Manager):  # pylint: disable=too-few-public-methods
    def get_queryset(self):
        # A lot of code assumes that this ordering takes place.
        # Don't remove it without careful analysis.
        return super().get_queryset().order_by("order", "id")


class DockerImageSetupCommand(models.Model):
    """This is a setup command that is reusable across multiple DockerImages.
    For example, installing Pip for the Python images, or setting up timezones
    in the Alpine images."""

    objects = DockerImageSetupCommandManager()

    name = models.CharField(
        null=False,
        blank=False,
        max_length=50,
        help_text="A short name describing what the command does. If the command is "
        "OS/language-specific, please use prefixes like this for consistency:"
        "'[OS:Alpine] Fix timezone setup', '[Lang:Python] Install virtualenv with Pip'",
    )

    command = models.TextField(
        null=False,
        blank=False,
        help_text="The command to run. Everything will be '&&'-ed together, so be careful about "
        "syntax errors.",
    )

    order = models.IntegerField(
        null=False,
        blank=False,
        help_text="This will be used to sort the setup commands (in ascending order). The "
        "following values are recommended for standardization: 0=OS-specific commands, "
        "1=language-specific commands; other values as required for specific use cases.",
    )

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "<DockerImageSetupCommand: " + str(self) + ">"


class DockerImageExtraPackage(models.Model):
    image = models.ForeignKey(
        "DockerImage", null=False, on_delete=models.CASCADE, related_name="extra_packages"
    )
    # Package name
    name = models.CharField(max_length=60, blank=False, null=False)

    def __str__(self) -> str:
        return "{} for {}".format(self.name, self.image.name)

    def __repr__(self) -> str:
        return "<DockerImageExtraPackage: " + str(self) + ">"

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
        # This domain was removed from the Site it was added to. All records of it should be
        # removed.
        ("deleted", "Deleted"),
        # Reserved domains we don't want people to use for legal/policy reasons (these should always
        # have site=None)
        ("blocked", "Blocked"),
    ]

    # Should ONLY be None for deleted or blocked domains
    site = models.ForeignKey(Site, null=True, on_delete=models.PROTECT)

    domain = models.CharField(
        max_length=255,
        validators=[
            RegexValidator(
                regex=r"^(?!(.*\.)?sites\.tjhsst\.edu$)"
                r"[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)+$$",
                message="Invalid domain. (Note: You can only have one sites.tjhsst.edu domain, and "
                "it must match the name of your site.)",
            )
        ],
    )

    created_time = models.DateTimeField(auto_now_add=True, null=False)
    creating_user = models.ForeignKey(get_user_model(), null=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=8, choices=STATUSES, default="active")

    def __str__(self) -> str:
        return "{} ({})".format(self.domain, self.site)

    def __repr__(self) -> str:
        return "<Domain: " + str(self) + ">"


class DatabaseHost(models.Model):
    # These should be capable of being put in a database URL
    # Hence "postgres", not "postgresql"
    DBMS_TYPES = [
        ("postgres", "PostgreSQL"),
        ("mysql", "MySQL"),
    ]

    # These parameters are passed to the containers to tell them how to connect to the database.
    hostname = models.CharField(max_length=255)
    port = models.PositiveIntegerField()

    dbms = models.CharField(max_length=16, choices=DBMS_TYPES)

    # These are used by the appservers to connect to and administer the database.
    # If either is unset, 'hostname' and 'port' are used, respectively. (Note that setting
    # admin_port=0 will also force a fallback on 'port'.)
    # If admin_hostname begins with a "/", it will be interpreted as a Unix socket path.
    admin_hostname = models.CharField(max_length=255, null=False, blank=True, default="")
    admin_port = models.PositiveIntegerField(null=True, blank=True, default=None)

    admin_username = models.CharField(max_length=255, null=False, blank=False)
    admin_password = models.CharField(max_length=255, null=False, blank=False)

    def serialize_for_appserver(self) -> Dict[str, Any]:
        return {
            "dbms": self.dbms,
            "admin_hostname": self.admin_hostname or self.hostname,
            "admin_port": self.admin_port or self.port,
            "admin_username": self.admin_username,
            "admin_password": self.admin_password,
        }

    def __str__(self) -> str:
        return "{}:{} ({})".format(self.hostname, self.port, self.get_dbms_display())

    def __repr__(self) -> str:
        return "<DatabaseHost: " + str(self) + ">"


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

    @property
    def redacted_db_url(self) -> str:
        return "{}://{}:***@{}:{}/{}".format(
            self.db_type, self.username, self.db_host, self.db_port, self.db_name
        )

    def serialize_for_appserver(self) -> Dict[str, Any]:
        return {
            "host": self.host.serialize_for_appserver(),
            "db_type": self.db_type,
            "db_host": self.db_host,
            "db_port": self.db_port,
            "username": self.username,
            "password": self.password,
            "db_name": self.db_name,
            "db_url": self.db_url,
        }

    def __str__(self) -> str:
        return self.redacted_db_url

    def __repr__(self) -> str:
        return "<Database: " + str(self) + ">"


class Operation(models.Model):
    """An Operation is a... well, operation being performed on a site. For example:
    - The initial site creation process
    - Renaming a site
    - Changing a site type

    A full list can be seen by looking at ``Operation.OPERATION_TYPES``, or by inspecting
    ``director/apps/sites/tasks.py`` or ``director/apps/sites/operations.py``.

    An Operation has one or more Actions. Each Action is an individual task that must be
    performed as part of an operation. The Action model only represents the state; the actual
    code is in ``director/apps/sites/actions.py``.

    Note: All of the actual state for the Operations and Actions is in the Celery tasks. The
    database entries are generated by the Celery tasks for easier inspection of running/failed
    tasks, but otherwise they are useless. As such, there is no way to "restart"/"continue" a failed
    Operation. (In almost all cases, you can and should run a "Fix site" task, which does its best
    to ensure that the site is set up properly based on its configuration in the database.)

    """

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
        # Tries to ensure everything is correct. Builds the Docker image, updates the
        # Docker service, and updates the Nginx configuration.
        ("fix_site", "Attempting to fix site"),
    ]

    site = models.OneToOneField(Site, null=False, on_delete=models.PROTECT)
    type = models.CharField(max_length=24, choices=OPERATION_TYPES)
    created_time = models.DateTimeField(auto_now_add=True, null=False)
    started_time = models.DateTimeField(null=True)

    @property
    def has_started(self) -> bool:
        return self.started_time is not None

    @property
    def has_failed(self) -> bool:
        return self.action_set.filter(result=False).exists()

    @property
    def is_failure_user_recoverable(self) -> bool:
        if not self.has_failed:
            return False

        # Return True if there is at least one failed action that is not recoverable.
        return not self.action_set.filter(result=False, user_recoverable=False).exists()

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
    # See Operation for a description of what this does.

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

    # None=Not finished, True=Successful, False=Failed
    result = models.BooleanField(null=True, default=None)
    # Some kind of message describing the actions taken or anything that failed in further detail.
    # *** ONLY VISIBLE TO SUPERUSERS ***
    # For example, if there was a syntax error in the Nginx config, this should contain the output
    # of the command run to check the Nginx config.
    # Should always be set for failed actions. Optional, but encouraged, for successful actions.
    message = models.TextField(null=False, blank=True)

    # If this is True, it indicates that the user is capable of recovering from a failure in this
    # action by interacting with the UI.
    # Operations that fail because of failures in Actions with this field set to True will not
    # be exported in the Prometheus metrics, and they will have a special note on the operations
    # page.
    # The main practical use of this is for building the Docker image, which will fail if the user
    # enters an incorrect package name. The image selection UI specially accounts for this case
    # and allows the user to re-submit and delete the operation.
    user_recoverable = models.BooleanField(null=False, default=False)

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
