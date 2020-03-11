# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "request"

urlpatterns = [
    path("", views.create_view, name="create"),
    path("approve/teacher/", views.approve_teacher_view, name="approve_teacher"),
    path("approve/admin/", views.approve_admin_view, name="approve_admin"),
    path("status/", views.status_view, name="status"),
]
