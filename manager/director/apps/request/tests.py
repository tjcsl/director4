# SPDX-License-Identifier: MIT
# (c) 2020 The TJHSST Director 4.0 Development Team & Contributors
from django.contrib.messages import get_messages
from django.urls import reverse

from ...test.director_test import DirectorTestCase
from ..users.models import User
from .models import SiteRequest


class RequestTest(DirectorTestCase):
    def test_approve_teacher_view(self):
        user = self.login(make_teacher=False)

        response = self.client.get(reverse("request:approve_teacher"), follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("You are not authorized to approve requests.", messages)

        user = self.login(make_teacher=True)

        response = self.client.get(reverse("request:approve_teacher"), follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertNotIn("You are not authorized to approve requests.", messages)

        student_user = User.objects.get_or_create(username="2020awilliam", is_student=True)[0]
        site_request = SiteRequest.objects.create(
            user=student_user, teacher=user, activity="Sysadmins", extra_information="Test!"
        )

        assert len(SiteRequest.objects.all()) == 1

        response = self.client.post(
            reverse("request:approve_teacher"), follow=True, data={"request": site_request.id + 1}
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn(
            "Either that site request does not exist or you do not have permission to approve it.",
            messages,
        )

        response = self.client.post(
            reverse("request:approve_teacher"), follow=True, data={"request": site_request.id}
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertNotIn(
            "Either that site request does not exist or you do not have permission to approve it.",
            messages,
        )

        response = self.client.post(
            reverse("request:approve_teacher"),
            follow=True,
            data={"request": site_request.id, "action": "accept"},
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Please check the agreement box to approve this site request!", messages)

        self.assertFalse(SiteRequest.objects.get(id=site_request.id).teacher_approval)

        response = self.client.post(
            reverse("request:approve_teacher"),
            follow=True,
            data={"request": site_request.id, "action": "accept", "agreement": True},
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertNotIn("Please check the agreement box to approve this site request!", messages)

        self.assertTrue(SiteRequest.objects.get(id=site_request.id).teacher_approval)

        response = self.client.post(
            reverse("request:approve_teacher"),
            follow=True,
            data={"request": site_request.id, "action": "reject"},
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertFalse(SiteRequest.objects.get(id=site_request.id).teacher_approval)
        self.assertIn("You have rejected this site request.", messages)

        site_request.delete()

    def test_approve_admin_view(self):
        user = self.login(make_teacher=True, make_admin=False)
        response = self.client.post(reverse("request:approve_admin"), follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Only administrators can perform the final approval.", messages)

        user = self.login(make_teacher=False, make_admin=True)

        student_user = User.objects.get_or_create(username="2020awilliam", is_student=True)[0]
        site_request = SiteRequest.objects.create(
            user=student_user,
            teacher=user,
            activity="Sysadmins",
            extra_information="Test!",
            teacher_approval=True,
        )

        assert len(SiteRequest.objects.all()) == 1

        response = self.client.post(
            reverse("request:approve_admin"), follow=True, data={"request": site_request.id + 1}
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn(
            "Either that site request does not exist or it has not been approved by a teacher.",
            messages,
        )

        response = self.client.post(
            reverse("request:approve_admin"),
            follow=True,
            data={
                "request": site_request.id,
                "action": "accept",
                "admin_comments": "admin comments test",
                "private_admin_comments": "private admin comments test",
            },
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Request marked as processed.", messages)

        self.assertEqual(
            "admin comments test", SiteRequest.objects.get(id=site_request.id).admin_comments
        )
        self.assertEqual(
            "private admin comments test",
            SiteRequest.objects.get(id=site_request.id).private_admin_comments,
        )
        self.assertTrue(SiteRequest.objects.get(id=site_request.id).admin_approval)

        site_request = SiteRequest.objects.get(id=site_request.id)
        site_request.teacher_approval = True
        site_request.admin_approval = None
        site_request.save()

        response = self.client.post(
            reverse("request:approve_admin"),
            follow=True,
            data={"request": site_request.id, "action": "reject"},
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Request marked as rejected.", messages)
        self.assertFalse(SiteRequest.objects.get(id=site_request.id).admin_approval)

    def test_status_view(self):
        user = self.login(accept_guidelines=True, make_student=False, make_teacher=True)
        response = self.client.get(reverse("request:status"), follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Only students can view this page.", messages)

        student_user = self.login(
            username="2020awilliam", accept_guidelines=True, make_student=True, make_teacher=False
        )
        response = self.client.get(reverse("request:status"), follow=True)
        self.assertEqual(0, len(response.context["site_requests"]))

        site_request = SiteRequest.objects.create(
            user=student_user, teacher=user, activity="Sysadmins", extra_information="test"
        )
        assert len(SiteRequest.objects.all()) == 1

        response = self.client.get(reverse("request:status"), follow=True)
        self.assertEqual(1, len(response.context["site_requests"]))

        self.assertIn(site_request, response.context["site_requests"])

    def test_create_view(self):
        user_teacher = self.login(accept_guidelines=True, make_student=False, make_teacher=True)
        response = self.client.get(reverse("request:create"), follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Only students can view this page.", messages)

        user_student = self.login(
            username="2020awilliam", accept_guidelines=True, make_student=True, make_teacher=False
        )
        response = self.client.get(reverse("request:create"), follow=True)
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertNotIn("Only students can view this page.", messages)

        response = self.client.post(
            reverse("request:create"),
            follow=True,
            data={
                "activity": "SysadminsTest",
                "extra_information": "hello",
                "student_agreement": True,
                "teacher": user_teacher.id,
            },
        )
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertIn("Website request created!", messages)

        site_request = SiteRequest.objects.filter(
            activity="SysadminsTest",
            extra_information="hello",
            user=user_student,
            teacher=user_teacher,
        )
        self.assertEqual(1, len(site_request))
