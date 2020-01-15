# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django import forms
from django.contrib.auth import get_user_model
from django.core import validators

from .models import Site


class SiteCreateForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        required=False, queryset=get_user_model().objects.filter(is_service=False)
    )

    class Meta:
        model = Site
        fields = ["name", "description", "type", "purpose", "users"]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "type": forms.Select(attrs={"class": "form-control"}),
            "purpose": forms.Select(attrs={"class": "form-control"}),
            "users": forms.Select(attrs={"class": "form-control"}),
        }

        help_texts = {
            "name": "Can only contain lowercase letters, numbers, and dashes. Names cannot start "
            "with a number, and dashes must go between two non-dash characters. Maximum length of "
            "32 characters.",
            "type": "If you want to run a custom server, like Node.js or Django, you will need to "
            "set this to Dynamic.",
        }


class SiteNamesForm(forms.Form):
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

    sites_domain_enabled = forms.BooleanField(
        label="Enable sites.tjhsst.edu domain", label_suffix="?",
    )

    @classmethod
    def build_for_site(cls, site: Site) -> "SiteNamesForm":
        return SiteNamesForm(
            {"name": site.name, "sites_domain_enabled": site.sites_domain_enabled}
        )


# These fields don't need to be applied specially, so we can use a Modelform
class SiteMetaForm(forms.ModelForm):
    class Meta:
        model = Site

        fields = ["description", "purpose"]

        widgets = {
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "purpose": forms.Select(attrs={"class": "form-control"}),
        }
