# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Mapping, Sequence

from celery import shared_task

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template


def send_email(  # pylint: disable=too-many-arguments
    text_template: str,
    html_template: str,
    context: Mapping[str, Any],
    subject: str,
    emails: Sequence[str],
    bcc: bool,
) -> None:
    text_plain = get_template(text_template).render(context)
    text_html = get_template(html_template).render(context)

    emails = list(emails)

    if emails:  # Don't try sending emails to nobody
        if settings.ENABLE_EMAIL_SEND:
            if (settings.DEBUG or settings.TESTING) and not settings.DEBUG_EMAIL_SEND:
                print(text_plain)
            else:
                _raw_send_email.delay(
                    subject=subject,
                    text_plain=text_plain,
                    text_html=text_html,
                    emails=list(emails),
                    bcc=bcc,
                )


@shared_task
def _raw_send_email(
    subject: str, text_html: str, text_plain: str, emails: Sequence[str], bcc: bool
) -> None:
    msg = EmailMultiAlternatives(
        subject=settings.EMAIL_SUBJECT_PREFIX + subject,
        body=text_plain,
        from_email=settings.EMAIL_FROM,
        reply_to=[settings.DIRECTOR_CONTACT_EMAIL],
        bcc=(emails if bcc else None),
        to=(None if bcc else emails),
    )
    msg.attach_alternative(text_html, "text/html")

    msg.send()
