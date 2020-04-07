# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib import admin

from .models import MassEmail, User

admin.site.register(User)
admin.site.register(MassEmail)
