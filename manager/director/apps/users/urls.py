# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("mass-email/", views.mass_email_view, name="mass_email"),
]
