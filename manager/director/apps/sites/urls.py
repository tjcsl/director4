# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import include, path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("prometheus-metrics", views.prometheus_metrics_view, name="prometheus-metrics"),
    path("operations/", views.operations_view, name="operations"),
    path("create/", views.create_view, name="create"),
    path("create/webdocs/", views.dummy_view, name="create_webdocs"),
    path("<int:site_id>/", views.info_view, name="info"),
    path("<int:site_id>/delete/", views.dummy_view, name="delete"),
    path("<int:site_id>/terminal/", views.terminal_view, name="terminal"),
    path("<int:site_id>/files/", views.dummy_view, name="editor"),
    path(
        "<int:site_id>/secrets/regenerate/",
        views.regenerate_secrets_view,
        name="regenerate_secrets",
    ),
    path(
        "<int:site_id>/nginx/regenerate-config",
        views.regen_nginx_config_view,
        name="regen_nginx_config",
    ),
    path("<int:site_id>/restart/", views.restart_view, name="restart_service"),
]

edit_patterns = [
    path("", views.edit_view, name="edit"),
    path("names/", views.edit_names_view, name="edit_names"),
    path("meta/", views.edit_meta_view, name="edit_meta"),
]

database_patterns = [
    path("create/", views.create_database_view, name="create_database"),
    path("shell/", views.dummy_view, name="database_shell"),
    path("delete/", views.delete_database_view, name="delete_database"),
]

urlpatterns.extend(
    [
        path("<int:site_id>/edit/", include(edit_patterns)),
        path("<int:site_id>/database/", include(database_patterns)),
    ]
)
