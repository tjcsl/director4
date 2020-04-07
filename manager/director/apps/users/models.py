# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone

from ...utils.emails import send_email as utils_send_email

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

    accepted_guidelines = models.BooleanField(default=False, null=False)

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

    def has_webdocs(self) -> bool:
        return self.site_set.filter(purpose="user").exists()

    def __str__(self) -> str:
        return self.username

    def __repr__(self) -> str:
        return "<User: {} ({})>".format(self.username, self.id)


class MassEmail(models.Model):
    limit_users = models.ManyToManyField(
        User,
        help_text="If this is empty, the email will be sent to ALL users!",
        related_name="+",
        blank=True,
    )

    subject = models.CharField(max_length=200, null=False, blank=False)

    text_html = models.TextField(null=False, blank=False)
    text_plain = models.TextField(null=False, blank=False)

    sender = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="sent_emails",
    )

    created_time = models.DateTimeField(auto_now_add=True, null=False)
    sent_time = models.DateTimeField(null=True, default=None)

    def send_email(self, *, mass_email_send_confirm: bool) -> None:
        assert mass_email_send_confirm is True

        send_users = self.limit_users if self.limit_users.exists() else User.objects.all()

        emails = send_users.values_list("email")

        self.sent_time = timezone.localtime()
        self.save(update_fields=["sent_time"])

        utils_send_email(
            text_template="emails/text_plain.txt",
            html_template="emails/text_html.html",
            context={"text_html": self.text_html, "text_plain": self.text_plain},
            subject=self.subject,
            emails=emails,
            bcc=True,
        )

    def __str__(self) -> str:
        return "{} at {}".format(self.subject, self.sent_time)
