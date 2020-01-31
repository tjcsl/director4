# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import secrets
import string

from django.conf import settings


def gen_database_password():
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(settings.DIRECTOR_DATABASE_PASSWORD_LENGTH))
