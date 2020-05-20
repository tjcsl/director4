# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth import user_logged_in
from django.dispatch import receiver

from .models import SitePendingUser


@receiver(user_logged_in)
def user_login(sender, user, request, **kwargs):  # pylint: disable=unused-argument
    try:
        pending_user = SitePendingUser.objects.get(username=user.username)
    except SitePendingUser.DoesNotExist:
        pass
    else:
        pending_user.process_and_delete(user)
