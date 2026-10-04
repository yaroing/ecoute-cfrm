import time
from django.core.management.base import BaseCommand
from adapters.worker import run


class Command(BaseCommand):
    help = "Traite l’outbox, les envois, les échéances et la purge."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, **options):
        while True:
            run()
            if options["once"]:
                return
            time.sleep(10)
