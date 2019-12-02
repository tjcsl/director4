# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models  # pylint: disable=unused-import # noqa


class Site(models.Model):
    SITE_TYPES = [
        ("static", "Static"),
        ("php", "PHP"),
        ("dynamic", "Dynamic"),
    ]

    PURPOSES = [
        ("legacy", "Legacy"),
        ("user", "User"),
        ("project", "Project"),
        ("activity", "Activity"),
        ("other", "Other"),
    ]

    # Website name
    name = models.CharField(max_length=32, unique=True)
    # Some kind of description.
    description = models.TextField(blank=True)

    # What runs on the site
    type = models.CharField(max_length=16, choices=SITE_TYPES)
    # What the site is created for
    purpose = models.CharField(max_length=16, choices=PURPOSES)
    # The port that Docker forwards to on the host
    port = models.IntegerField(unique=True)
    # The Docker image running on here
    docker_image = models.ForeignKey("DockerImage", null=False, on_delete=models.PROTECT)
    # Users who have access to this site
    users = models.ManyToManyField(get_user_model())

    # The path to the process (either absolute or relative to `/site` within the Docker container)
    # to launch (for dynamic sites)
    process_path = models.CharField(max_length=100, null=False, blank=True)

    # Whether to enable access via the <name>.sites.tjhsst.edu domain
    sites_domain_enabled = models.BooleanField(default=True)

    # The site database
    database = models.OneToOneField(
        "Database", null=True, on_delete=models.SET_NULL, related_name="site"
    )

    @property
    def site_path(self) -> str:
        return "/web/site-{}".format(self.id)


class DockerImage(models.Model):
    # Examples: legacy_director_dynamic, site_1
    name = models.CharField(max_length=32, blank=False, null=False, unique=True)
    # True if created by a user, False if created by a Director admin
    is_custom = models.BooleanField(null=False)


class DockerImageExtraPackage(models.Model):
    image = models.ForeignKey(
        "DockerImage", null=False, on_delete=models.CASCADE, related_name="extra_packages"
    )
    # Package name
    name = models.CharField(max_length=60, blank=False, null=False, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["image", "name"], name="unique_image_package")
        ]


class Domain(models.Model):
    """Represents a custom (non-`sites.tjhsst.edu`) domain.

    `sites.tjhsst.edu` domains MUST be set up by creating a site with that name and setting
    sites_domain_enabled=True

    Note: It must be ensured that *.tjhsst.edu domains can only be set up by Director admins.

    """

    STATUSES = [
        # Enabled (most domains)
        ("active", "Active"),
        # Disabled (respected in generation of configuration, but currently no provisions for
        # setting domains to inactive)
        ("inactive", "Inactive",),
        # Reserved domains we don't want people to use for legal/policy reasons (these should always
        # have site=None)
        ("blocked", "Blocked",),
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
        # Change the site type (example: static -> dynamic)
        ("change_site_type", "Changing site type",),
        # Change in custom domains
        ("change_site_domains", "Changing site domains"),
        # Something was changed that requires the Nginx config to be regenerated and saved, but no
        # other changes.
        ("regen_nginx_config", "Regenerating Nginx configuration",),
        # Create a database for the site
        ("create_site_database", "Creating site database"),
        # Create a database for the site
        ("delete_site_database", "Deleting site database"),
        # Regenerate the database password.
        ("regen_database_password", "Regenerating database password",),
        # Delete a site, its files, its database, its Docker image, etc.
        ("delete_site", "Deleting site",),
    ]

    site = models.OneToOneField(Site, null=False, on_delete=models.PROTECT)
    type = models.CharField(max_length=16, choices=OPERATION_TYPES)
    started_time = models.DateTimeField(auto_now_add=True, null=False)

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


class Action(models.Model):
    operation = models.ForeignKey(Operation, null=False, on_delete=models.PROTECT)

    # Example: "update_nginx_config"
    slug = models.CharField(max_length=32, null=False, blank=False)
    # May be displayed to the user for progress updates. Example: "Updating Nginx config"
    name = models.CharField(max_length=32, null=False, blank=False)
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

    @property
    def finished(self) -> bool:
        return self.result is not None

    @property
    def succeeded(self) -> bool:
        return self.result is True

    @property
    def failed(self) -> bool:
        return self.result is False
