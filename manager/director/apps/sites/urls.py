# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("<int:site_id>/", views.info_view, name="info"),
]
