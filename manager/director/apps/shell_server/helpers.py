# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import base64
import json
import os
import tempfile
from typing import Optional, Union

import pexpect

from django.conf import settings
from django.contrib.auth import get_user_model

from directorutil import crypto

from ..sites.models import Site
from ..users.models import User  # ONLY imported for type checks. Not for other use.


def authenticate_kinit(username: str, password: str) -> Optional[User]:
    try:
        user = get_user_model().objects.get(username=username)
    except get_user_model().DoesNotExist:
        return None

    krb5ccname = None
    try:
        krb5cc_fd, krb5ccname = tempfile.mkstemp(prefix="shell-kerberos-auth-", text=False)
        os.close(krb5cc_fd)

        proc = pexpect.spawn(
            "/usr/bin/kinit",
            ["-c", krb5ccname, "{}@{}".format(username, settings.SHELL_AUTH_KINIT_REALM)],
            timeout=settings.SHELL_AUTH_KINIT_TIMEOUT,
            encoding="utf-8",
        )

        proc.expect(":")
        proc.sendline(password)

        returned = proc.expect([pexpect.EOF, "password:"])
        if returned == 1:
            # Expired
            return None

        proc.close()

        if proc.exitstatus != 0:
            return None

        return user
    except pexpect.TIMEOUT:
        return None
    finally:
        if krb5ccname and os.path.exists(krb5ccname):
            os.remove(krb5ccname)


def generate_token(site: Site, *, expire_time: Union[int, float]) -> bytes:
    # The anatomy of a token:
    # "<base64-encoded encrypted message>\n<base64-encoded signature of encrypted message>"
    site_data = site.serialize_for_appserver()
    site_data["token_expire_time"] = expire_time
    msg = json.dumps(site_data).encode()

    encrypted_msg = crypto.encrypt_message(
        msg=msg, public_key=settings.SHELL_ENCRYPTION_TOKEN_PUBLIC_KEY
    )

    signature = crypto.sign_message(
        msg=encrypted_msg, private_key=settings.SHELL_SIGNING_TOKEN_PRIVATE_KEY
    )

    return base64.b64encode(encrypted_msg) + b"\n" + base64.b64encode(signature)
