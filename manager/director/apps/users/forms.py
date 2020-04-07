# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django import forms

from .models import MassEmail


class MassEmailForm(forms.ModelForm):
    confirm_send = forms.BooleanField(
        required=True,
        help_text="Are you sure you want to send this email to potentially hundreds of users?",
    )

    class Meta:
        model = MassEmail

        fields = ["limit_users", "subject", "text_html", "text_plain"]

        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "text_html": forms.Textarea(attrs={"class": "form-control"}),
            "text_plain": forms.Textarea(attrs={"class": "form-control"}),
        }
