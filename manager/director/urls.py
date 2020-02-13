# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

"""director URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("social_django.urls", namespace="social")),
    path("", include("director.apps.auth.urls", namespace="auth")),
    path("sites/", include("director.apps.sites.urls", namespace="sites")),
    path("docs/", include("director.apps.docs.urls", namespace="docs")),
]

if settings.DEBUG:
    urlpatterns.append(path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.ico")))
