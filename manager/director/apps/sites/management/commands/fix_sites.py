import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from director.apps.sites.models import Operation, Site
from director.apps.sites.operations import fix_site


class Command(BaseCommand):
    help = "Run 'fix' operations on all sites"

    def add_arguments(self, parser):
        parser.add_argument("--start-id", type=int, default=1)

    def handle(self, *args: Any, **options: Any) -> None:
        for site in Site.objects.filter(id__gte=options["start_id"]).order_by("id"):
            if Operation.objects.filter(site=site).exists():
                self.stdout.write(
                    "Site {} (id {}) already has an operation running; waiting for "
                    "completion...".format(site.name, site.id)
                )

                self.wait_for_operation(site)

            print("Running 'fix' operation on site {} (id {})".format(site.name, site.id))
            fix_site(site)

            self.wait_for_operation(site)

    def wait_for_operation(self, site: Site) -> None:
        while True:
            try:
                operation = Operation.objects.get(site_id=site.id)
            except Operation.DoesNotExist:
                # Finished
                print("Operation finished on site {} (id {})".format(site.name, site.id))
                return

            if operation.has_failed:
                raise CommandError("Operation failed on site {} (id {})".format(site.name, site.id))

            time.sleep(1)
