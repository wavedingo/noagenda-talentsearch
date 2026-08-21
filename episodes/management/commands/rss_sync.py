from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from episodes.models import FeedSyncRun
from episodes.sync import sync_feed


class Command(BaseCommand):
    help = "Fetch the No Agenda RSS feed and upsert episodes (runs every 30 minutes in production)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and parse, report what would change, write nothing.",
        )
        parser.add_argument(
            "--url",
            default=settings.RSS_FEED_URL,
            help="Feed URL to sync (defaults to RSS_FEED_URL).",
        )

    def handle(self, *args, **options):
        run = sync_feed(options["url"], dry_run=options["dry_run"])

        prefix = "[dry run] " if options["dry_run"] else ""
        if run.status == FeedSyncRun.Status.FAILED:
            # Non-zero exit so the cron job's own alerting sees the failure too.
            raise CommandError(f"{prefix}sync failed: {run.error}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{run.items_seen} items: "
                f"{run.episodes_created} created, {run.episodes_updated} updated, "
                f"{run.items_below_floor} below floor, {run.items_failed} unparseable"
            )
        )
