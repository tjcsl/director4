# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "request"

urlpatterns = [
    path("", views.create_view, name="create"),
    path("approve", views.approve_view, name="approve"),
]
