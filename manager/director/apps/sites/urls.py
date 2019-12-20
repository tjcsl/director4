# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("demo/", views.demo_view, name="demo"),
    path("create/", views.create_view, name="create"),
    path("create/webdocs/", views.dummy_view, name="create_webdocs"),
    path("<int:site_id>/", views.info_view, name="info"),
    path("<int:site_id>/rename/", views.rename_view, name="rename"),
    path("<int:site_id>/edit/", views.dummy_view, name="edit"),
    path("<int:site_id>/delete/", views.dummy_view, name="delete"),
    path("<int:site_id>/terminal/", views.dummy_view, name="web_terminal"),
    path("<int:site_id>/files/", views.dummy_view, name="editor"),
    path("<int:site_id>/install/", views.dummy_view, name="install_options"),
    path("<int:site_id>/config/", views.dummy_view, name="config"),
    path("<int:site_id>/permission/", views.dummy_view, name="permissions"),
    path("<int:site_id>/database/create/", views.dummy_view, name="create_database"),
    path("<int:site_id>/database/edit/", views.dummy_view, name="edit_database"),
    path("<int:site_id>/database/delete/", views.dummy_view, name="delete_database"),
    path("<int:site_id>/process/create/", views.dummy_view, name="create_process"),
    path("<int:site_id>/process/edit/", views.dummy_view, name="edit_process"),
    path("<int:site_id>/process/delete/", views.dummy_view, name="delete_process"),
]
