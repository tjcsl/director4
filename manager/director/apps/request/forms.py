# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.safestring import mark_safe

from .models import SiteRequest


class SiteRequestForm(forms.ModelForm):
    teacher = forms.ModelChoiceField(
        required=True,
        queryset=get_user_model().objects.filter(is_teacher=True),
        help_text="This teacher will be emailed with instructions to approve your site request.",
    )

    student_agreement = forms.BooleanField(
        required=True, help_text=mark_safe(settings.DIRECTOR_SITE_STUDENT_AGREEMENT_HELP_TEXT),
    )

    class Meta:
        model = SiteRequest

        fields = ["activity", "extra_information", "teacher"]

        help_texts = {
            "activity": "The name of the activity on behalf of which you are requesting the site.",
            "extra_information": "Please enter any additional information you want the teacher or "
            "the Sysadmins to know.",
        }

        widgets = {
            "activity": forms.TextInput(attrs={"class": "form-control"}),
            "extra_information": forms.TextInput(attrs={"class": "form-control"}),
        }
