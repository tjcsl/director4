# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from django import forms
from django.contrib.auth import get_user_model

from .models import SiteRequest


class SiteRequestForm(forms.ModelForm):
    teacher = forms.ModelChoiceField(
        required=True,
        queryset=get_user_model().objects.filter(is_teacher=True),
        help_text="This teacher will be emailed with instructions to approve your site request.",
    )

    student_agreement = forms.BooleanField(
        required=True,
        help_text="I have read, understood, and agree to abide by the rules outlined in the "
        "Computer Systems Lab Policy, the TJHSST World-Wide Website Guidelines, the FCPS "
        "Acceptable Use Policy, and the FCPS Student Rights and Responsibilities. I understand "
        "that the above services may be revoked at any time and other disciplinary actions may "
        "occur if I directly or indirectly violate any guidelines as outlined in the above "
        "policies.",
    )

    class Meta:
        model = SiteRequest

        fields = ["activity", "extra_information", "teacher"]

        help_texts = {
            "activity": "The name of the activity on behalf of which you are requesting the site.",
            "extra_information": "Is there any additional information you want the teacher or the "
            "Syadmins to know?",
        }

        widgets = {
            "activity": forms.TextInput(attrs={"class": "form-control"}),
            "extra_information": forms.TextInput(attrs={"class": "form-control"}),
        }
