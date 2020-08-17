from typing import Any

from django.core.management.base import BaseCommand

from director.apps.users.models import User


class Command(BaseCommand):
    help = "Run 'fix' operations on all sites"

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args: Any, **options: Any) -> None:
        user = User.objects.get(username=options["username"])
        user.is_superuser = True
        user.save()

        self.stdout.write("{} is now a superuser\n".format(user.username))
