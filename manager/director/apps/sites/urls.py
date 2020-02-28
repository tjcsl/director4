# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import include, path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.sites.index_view, name="index"),
    path(
        "prometheus-metrics", views.maintenance.prometheus_metrics_view, name="prometheus-metrics"
    ),
    path("operations/", views.maintenance.operations_view, name="operations"),
    path(
        "operations/<int:operation_id>/delete-and-fix",
        views.maintenance.operation_delete_fix_view,
        name="operation-delete-fix",
    ),
    path(
        "custom-resource-limits/",
        views.maintenance.custom_resource_limits_list_view,
        name="custom_resource_limits_list",
    ),
    path("create/", views.sites.create_view, name="create"),
    path("create/webdocs/", views.sites.dummy_view, name="create_webdocs"),
    path("<int:site_id>/", views.sites.info_view, name="info"),
    path("<int:site_id>/image/select/", views.sites.image_select_view, name="image_select"),
    path("<int:site_id>/delete/", views.sites.delete_view, name="delete"),
    path("<int:site_id>/terminal/", views.sites.terminal_view, name="terminal"),
    path(
        "<int:site_id>/secrets/regenerate/",
        views.sites.regenerate_secrets_view,
        name="regenerate_secrets",
    ),
    path(
        "<int:site_id>/nginx/regenerate-config",
        views.sites.regen_nginx_config_view,
        name="regen_nginx_config",
    ),
    path("<int:site_id>/restart/", views.sites.restart_view, name="restart_service"),
    # Admin-only
    path(
        "<int:site_id>/resource-limits/",
        views.maintenance.resource_limits_view,
        name="resource_limits",
    ),
]

edit_patterns = [
    path("", views.edit.edit_view, name="edit"),
    path("names/", views.edit.edit_names_view, name="edit_names"),
    path("meta/", views.edit.edit_meta_view, name="edit_meta"),
]

database_patterns = [
    path("create/", views.database.create_database_view, name="create_database"),
    path("shell/", views.database.database_shell_view, name="database_shell"),
    path("delete/", views.database.delete_database_view, name="delete_database"),
]

file_patterns = [
    path("", views.sites.dummy_view, name="editor"),
    path("get/", views.files.get_file_view, name="get_file"),
    path("write/", views.files.write_file_view, name="write_file"),
    path("rm/", views.files.remove_file_view, name="remove_file"),
    path("rmdir-recur/", views.files.remove_directory_recur_view, name="remove_directory_recur"),
    path("mkdir/", views.files.make_directory_view, name="mkdir"),
    path("chmod/", views.files.chmod_view, name="chmod"),
    path("rename/", views.files.rename_view, name="rename"),
]

urlpatterns.extend(
    [
        path("<int:site_id>/edit/", include(edit_patterns)),
        path("<int:site_id>/database/", include(database_patterns)),
        path("<int:site_id>/files/", include(file_patterns)),
    ]
)
