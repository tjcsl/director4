# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django import forms
from django.core import validators


class SiteRenameForm(forms.Form):
    name = forms.CharField(
        label="Name",
        max_length=32,
        validators=[
            validators.MinLengthValidator(2),
            validators.RegexValidator(
                regex=r"^[a-z0-9]+(-[a-z0-9]+)*$",
                message="Site names must consist of lowercase letters, numbers, and dashes. Dashes "
                "must go between two non-dash characters.",
            ),
        ],
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
