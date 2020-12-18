from django.contrib.auth import get_user_model
from django.test import TestCase


class DirectorTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    # pylint: disable=too-many-arguments
    def login(
        self,
        username="awilliam",
        accept_guidelines=False,
        make_admin=False,
        make_teacher=False,
        make_student=False,
    ):
        """
        Login as the specified user

        Args:
            username: Username to log in as
            accept_guidelines: Whether to accept guidelines or not.
            make_admin: Whether to make this user an admin.
            make_teacher: Whether to make this user a teacher.
            make_student: Whether to make this user a student.

        Returns: The user corresponding to `username`

        """
        user = get_user_model().objects.get_or_create(username=username)[0]
        self.client.force_login(user)

        user.accepted_guidelines = accept_guidelines
        user.is_superuser = make_admin
        user.is_teacher = make_teacher
        user.is_student = make_student

        user.save()

        return user
