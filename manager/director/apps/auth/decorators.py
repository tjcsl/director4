# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib.auth.decorators import user_passes_test

superuser_required = user_passes_test(lambda user: user.is_authenticated and user.is_superuser)
