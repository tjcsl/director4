# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..auth.decorators import require_accept_guidelines, superuser_required
from .forms import MassEmailForm


@superuser_required
@require_accept_guidelines
def mass_email_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = MassEmailForm(request.POST)
        if form.is_valid():
            mass_email = form.save(commit=False)
            mass_email.sender = request.user
            mass_email.save()
            form.save_m2m()

            mass_email.send_email(mass_email_send_confirm=True)

            messages.success(request, "Mass email sent.")

            return redirect("sites:management")
    else:
        form = MassEmailForm()

    context = {
        "form": form,
    }

    return render(request, "users/mass_email.html", context)
