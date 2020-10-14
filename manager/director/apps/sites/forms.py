# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import re
import string
from typing import Any, Dict

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import validators
from django.utils.safestring import mark_safe

from .models import (
    DatabaseHost,
    DockerImage,
    DockerImageExtraPackage,
    DockerImageSetupCommand,
    Site,
)


class SiteCreateForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        required=False, queryset=get_user_model().objects.filter(is_service=False)
    )

    student_agreement = forms.BooleanField(
        required=True, help_text=mark_safe(settings.DIRECTOR_SITE_STUDENT_AGREEMENT_HELP_TEXT),
    )

    def __init__(self, *args: Any, user: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.user = user

        if not user.is_superuser:
            # Non-superusers cannot edit the site purpose.
            try:
                self.initial_purpose = self.get_initial_for_field(self.fields["purpose"], "purpose")
                if self.initial_purpose is None:
                    raise KeyError
            except KeyError:
                self.initial_purpose = "project"

            # The template checks this specifically, so we need it to be set
            self.fields["purpose"].initial = self.initial_purpose
            self.fields["purpose"].disabled = True

            self.fields["users"].initial = [user]

            if self.initial_purpose == "user":
                # And for user-specific sites, they cannot edit the name or the user list.
                self.fields["name"].initial = user.username
                self.fields["name"].disabled = True

                self.fields["users"].disabled = True
        else:
            self.initial_purpose = None

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()

        if (
            cleaned_data["name"][0] in string.digits
            and cleaned_data.get("purpose", self.initial_purpose) != "user"
        ):
            self.add_error("name", "Project site names cannot start with a number")

        if len(cleaned_data.get("users", [])) == 0:
            self.add_error("users", "You must select at least one user for this site")

        if (
            "users" in cleaned_data.keys()
            and self.user not in cleaned_data["users"]
            and not self.user.is_superuser
        ):
            self.add_error("users", "You must include yourself as a user for this site")

        return cleaned_data

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
            "name": "Can only contain lowercase letters, numbers, and dashes. Dashes must go "
            "between two non-dash characters. Maximum length of "
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

    def __init__(self, *args: Any, site: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.site = site

        self.fields["name"].initial = site.name
        if site.purpose == "user":
            self.fields["name"].disabled = True

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()

        if cleaned_data["name"][0] in string.digits and self.site.purpose != "user":
            self.add_error("name", "Project site names cannot start with a number")

        return cleaned_data


class DomainForm(forms.Form):
    domain = forms.CharField(
        label="Custom domain",
        max_length=255,
        required=False,
        validators=[
            validators.RegexValidator(
                regex=r"^(?!(.*\.)?sites\.tjhsst\.edu$)[0-9a-zA-Z_\- .]+$",
                message="You can only have one sites.tjhsst.edu domain, the automatically generated"
                " one that matches the name of your site.",
            ),
        ],
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args: Any, user_is_superuser: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.user_is_superuser = user_is_superuser

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()

        if not self.user_is_superuser:
            if "domain" in cleaned_data and cleaned_data["domain"].endswith("tjhsst.edu"):
                self.add_error("domain", "Only administrators can add tjhsst.edu domains")

        return cleaned_data


DomainFormSet = forms.formset_factory(DomainForm)  # type: ignore


class SiteTypeForm(forms.Form):
    type = forms.ChoiceField(
        choices=Site.SITE_TYPES, widget=forms.Select(attrs={"class": "form-control"}),
    )


# These fields don't need to be applied specially, so we can use a Modelform
class SiteMetaForm(forms.ModelForm):
    def __init__(self, *args: Any, user: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if not user.is_superuser:
            self.fields["purpose"].disabled = True

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()

        if self.instance.name[0] in string.digits and cleaned_data["purpose"] != "user":
            self.add_error("name", "Project site names cannot start with a number")

        return cleaned_data

    class Meta:
        model = Site

        fields = ["description", "purpose", "users"]

        widgets = {
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "purpose": forms.Select(attrs={"class": "form-control"}),
        }


class DatabaseCreateForm(forms.Form):
    host = forms.ModelChoiceField(
        queryset=DatabaseHost.objects.all(), widget=forms.RadioSelect(), empty_label=None
    )


class ImageSelectForm(forms.Form):
    image = forms.ChoiceField(
        choices=lambda: DockerImage.objects.filter_user_visible()  # type: ignore
        .order_by("friendly_name")
        .values_list("name", "friendly_name"),
        required=True,
        widget=forms.widgets.RadioSelect(),
    )

    write_run_sh_file = forms.BooleanField(
        label="Write run.sh file",
        label_suffix="?",
        required=False,
        help_text="Based on the image you selected, this will write a sample run.sh file.\n"
        "WARNING: If you've already created a run.sh file, it will be overwritten.",
    )

    packages = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="This should be a space-separated list of packages to install in the image.",
    )

    PACKAGE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_][-_a-zA-Z0-9]*$")

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()

        # Make sure the package names can all fit in the name field
        max_package_name_length = DockerImageExtraPackage._meta.get_field("name").max_length
        package_names = cleaned_data["packages"].strip().split()
        if any(len(name) > max_package_name_length for name in package_names):
            self.add_error("packages", "One of your package names is too long")
        if any(self.PACKAGE_NAME_REGEX.search(name) is None for name in package_names):
            self.add_error("packages", "One of your package names is invalid")

        return cleaned_data


class SiteResourceLimitsForm(forms.Form):
    cpus = forms.FloatField(
        required=False,
        min_value=0,
        max_value=3,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Fractions of a CPU to allocate",
    )

    mem_limit = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Memory limit (bytes/KiB/MIB/GiB/KB/MB/GB)",
        validators=[
            validators.RegexValidator(
                regex=r"^(\d+(\s*[KMG]i?B)?)?$",
                message="Must be either 1) blank for the default limit or 2) a number followed by "
                "one of the suffixes KiB, MiB, or GiB (powers of 1024) or KB, MB, GB (powers of "
                "1000).",
            ),
        ],
    )

    client_body_limit = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Client body (aka file upload) size limit",
        validators=[
            validators.RegexValidator(
                regex=r"^(\d+[kKmM]?)?$",
                message="Must be either 1) blank for the default limit or 2) a number, optionally "
                "followed by one of the suffixes k/K or m/M.",
            ),
        ],
    )

    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Why is this site being given custom resource limits?",
    )


class SiteAvailabilityForm(forms.Form):
    availability = forms.ChoiceField(
        required=False,
        choices=Site.AVAILABILITIES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class DockerImageForm(forms.ModelForm):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if self.instance is not None and self.instance.id is not None:
            self.fields["name"].disabled = True
            self.fields["name"].help_text = "You cannot edit the names of existing images."

    class Meta:
        model = DockerImage

        fields = [
            "name",
            "friendly_name",
            "description",
            "logo_url",
            "is_user_visible",
            "setup_commands",
            "base_install_command",
            "install_command_prefix",
            "run_script_template",
        ]

        labels = {"is_user_visible": "Visible to users?"}

        help_texts = {
            "is_user_visible": "If this is not set, users will not be able to select this image "
            "for their sites.",
        }

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "friendly_name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "logo_url": forms.URLInput(attrs={"class": "form-control"}),
            "setup_commands": forms.SelectMultiple(attrs={"class": "form-control"}),
            "base_install_command": forms.TextInput(attrs={"class": "form-control"}),
            "install_command_prefix": forms.TextInput(attrs={"class": "form-control"}),
            "run_script_template": forms.Textarea(attrs={"class": "form-control monospace"}),
        }


class DockerImageSetupCommandForm(forms.ModelForm):
    class Meta:
        model = DockerImageSetupCommand

        fields = ["name", "command", "order"]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "command": forms.TextInput(attrs={"class": "form-control"}),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
        }
