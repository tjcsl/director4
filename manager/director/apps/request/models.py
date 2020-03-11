# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


class SiteRequest(models.Model):
    user = models.ForeignKey(
        get_user_model(), related_name="requested_sites", on_delete=models.CASCADE, null=False
    )
    teacher = models.ForeignKey(
        get_user_model(), related_name="site_requests", on_delete=models.CASCADE, null=False
    )

    request_date = models.DateTimeField(auto_now_add=True, null=False)

    teacher_approval = models.BooleanField(null=True, default=None)
    admin_approval = models.BooleanField(null=True, default=None)

    # WILL be shown to users.
    admin_comments = models.TextField(null=False, blank=True)
    # Will NOT be shown to users
    private_admin_comments = models.TextField(null=False, blank=True)

    activity = models.CharField(max_length=32, null=False, blank=False)
    extra_information = models.TextField(null=False, blank=True)

    def __str__(self) -> str:
        return "{}, requested on {}, approval statuses: {} {}".format(
            self.activity,
            timezone.localtime(self.request_date).strftime("%Y-%m-%d at %I:%M %p"),
            self.teacher_approval,
            self.admin_approval,
        )

    def __repr__(self) -> str:
        return "<SiteRequest: {}>".format(self)
