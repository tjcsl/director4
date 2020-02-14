from typing import Any, Dict

from django import forms
from django.contrib.auth import get_user_model
from django.core import validators

from .models import DatabaseHost, DockerImage, DockerImageExtraPackage, Site


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
        return SiteNamesForm({"name": site.name, "sites_domain_enabled": site.sites_domain_enabled})


class DomainForm(forms.Form):
    domain = forms.CharField(
        label="Custom domain",
        max_length=255,
        required=False,
        validators=[
            validators.RegexValidator(
                regex=r"^(?!(.*\.)?sites\.tjhsst\.edu$)[0-9a-zA-Z_\- .]+$",
                message="You can only have one sites.tjhsst.edu domain, and it must match the name "
                "of your site.",
            ),
        ],
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


DomainFormSet = forms.formset_factory(DomainForm)  # type: ignore


# These fields don't need to be applied specially, so we can use a Modelform
class SiteMetaForm(forms.ModelForm):
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
        required=False,
        widget=forms.widgets.RadioSelect(),
    )

    write_run_sh_file = forms.BooleanField(
        label="Write run.sh file",
        label_suffix="?",
        required=False,
        help_text="Based on the image you selected, this will write a sample run.sh file. "
        "If you've already created a run.sh file, it will be overwritten.",
    )

    packages = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="This should be a space-separated list of packages to install in the image.",
    )

    def clean(self) -> Dict[str, Any]:
        cleaned_data = super().clean()

        # Make sure the package names can all fit in the name field
        max_package_name_length = DockerImageExtraPackage._meta.get_field("name").max_length
        package_names = cleaned_data["packages"].strip().split()
        if any(len(name) > max_package_name_length for name in package_names):
            self.add_error("packages", "One of your package names is too long")

        return cleaned_data
