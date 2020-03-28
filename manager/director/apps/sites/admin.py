# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib import admin

from .models import (
    Action,
    Database,
    DatabaseHost,
    DockerImage,
    DockerImageExtraPackage,
    DockerImageSetupCommand,
    Domain,
    Operation,
    Site,
    SiteResourceLimits,
)

admin.site.register(DockerImage)
admin.site.register(DockerImageSetupCommand)
admin.site.register(DockerImageExtraPackage)
admin.site.register(Domain)

admin.site.register(DatabaseHost)
admin.site.register(Database)

admin.site.register(Site)
admin.site.register(SiteResourceLimits)

admin.site.register(Operation)
admin.site.register(Action)
