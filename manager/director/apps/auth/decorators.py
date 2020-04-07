# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import functools
from typing import Any, Callable, Union

from django.contrib.auth.decorators import user_passes_test
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect

superuser_required = user_passes_test(lambda user: user.is_authenticated and user.is_superuser)


def require_accept_guidelines(
    func: Callable[..., Union[HttpResponse, StreamingHttpResponse]]
) -> Callable[..., Union[HttpResponse, StreamingHttpResponse]]:
    @functools.wraps(func)
    def wrapper(
        request: HttpRequest, *args: Any, **kwargs: Any
    ) -> Union[HttpResponse, StreamingHttpResponse]:
        if request.user.is_authenticated and not request.user.accepted_guidelines:
            return redirect("auth:accept_guidelines")

        return func(request, *args, **kwargs)

    return wrapper


def require_accept_guidelines_no_redirect(
    func: Callable[..., Union[HttpResponse, StreamingHttpResponse]]
) -> Callable[..., Union[HttpResponse, StreamingHttpResponse]]:
    @functools.wraps(func)
    def wrapper(
        request: HttpRequest, *args: Any, **kwargs: Any
    ) -> Union[HttpResponse, StreamingHttpResponse]:
        if request.user.is_authenticated and not request.user.accepted_guidelines:
            return HttpResponse(status=401)

        return func(request, *args, **kwargs)

    return wrapper
