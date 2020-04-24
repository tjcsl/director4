# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "shell_server"

urlpatterns = [
    path("authenticate/", views.authenticate_view, name="authenticate"),
]
