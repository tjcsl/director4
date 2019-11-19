# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models

logger = logging.getLogger(__name__)


class UserManager(DjangoUserManager):
    pass


class User(AbstractBaseUser):
    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "email", "is_teacher"]

    id = models.AutoField(primary_key=True)

    username = models.CharField(unique=True, max_length=32, null=False, blank=False)
    first_name = models.CharField(max_length=35, null=False, blank=False)
    last_name = models.CharField(max_length=70, null=False, blank=False)
    email = models.EmailField(max_length=50, null=False, blank=False)

    is_active = models.BooleanField(default=True, null=False)
    is_service = models.BooleanField(default=False, null=False)
    is_student = models.BooleanField(default=False, null=False)
    is_teacher = models.BooleanField(default=False, null=False)
    is_superuser = models.BooleanField(default=False, null=False)
    _is_staff = models.BooleanField(default=False, null=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    def has_perm(self, perm: str, obj: Any = None) -> bool:  # pylint: disable=unused-argument
        return self.is_superuser

    def has_module_perms(self, app_label: str) -> bool:  # pylint: disable=unused-argument
        return self.is_superuser

    @property
    def is_staff(self) -> bool:
        return self._is_staff or self.is_superuser

    @is_staff.setter
    def is_staff(self, staff: bool) -> None:
        self._is_staff = staff

    @property
    def full_name(self) -> str:
        return self.first_name + " " + self.last_name

    @property
    def short_name(self) -> str:
        return self.first_name

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.short_name

    def get_social_auth(self):
        return self.social_auth.get(provider="ion")

    def __str__(self) -> str:
        return self.username

    def __repr__(self) -> str:
        return "<User: {} ({})>".format(self.username, self.id)
