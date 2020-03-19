# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.urls import path

from . import views

app_name = "docs"

urlpatterns = [
    path("", views.doc_page_view, name="index"),
    path("-/search/", views.search_view, name="search"),
    path("<path:page_name>/", views.doc_page_view, name="doc_page"),
]
