"""Transcode backstop.

Uploads normally transcode in a background thread the moment they land; this
command exists so nothing depends on that thread surviving. It requeues demos
abandoned mid-transcode by a deploy or a crash, then drains whatever is waiting.
Safe to run at any time, from anywhere, concurrently with the web process --
claiming is a conditional UPDATE, so no demo is ever processed twice.
"""

from django.core.management.base import BaseCommand

from candidates import tasks
from candidates.models import Demo


class Command(BaseCommand):
    help = "Transcode queued demo uploads and requeue any abandoned mid-transcode."

    def add_arguments(self, parser):
        parser.add_argument("--demo-id", type=int, help="Process just this demo, if it is queued.")

    def handle(self, *args, **options):
        demo_id = options.get("demo_id")
        if demo_id:
            demo = tasks.process_demo(demo_id)
            if demo is None:
                self.stdout.write(f"Demo {demo_id} was not queued; nothing to do.")
                return
            if demo.processing_state == Demo.ProcessingState.FAILED:
                self.stdout.write(self.style.ERROR(f"Demo {demo_id} failed: {demo.processing_error}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Demo {demo_id} is ready."))
            return

        processed, failed = tasks.drain_queue()
        summary = f"Processed {processed} demo(s); {failed} failed."
        self.stdout.write(self.style.WARNING(summary) if failed else self.style.SUCCESS(summary))
