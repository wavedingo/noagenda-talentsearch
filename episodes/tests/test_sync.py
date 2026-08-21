"""Sync behaviour: idempotency, the episode floor, and failure containment."""

from unittest.mock import patch

import requests
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase

from core.models import Settings
from episodes.models import Episode, FeedSyncRun
from episodes.sync import ALERT_AFTER_CONSECUTIVE_FAILURES, sync_feed

from .test_feed_parsing import load_fixture

FEED_URL = "https://feeds.example.com/noagenda.xml"


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code


def feed_ok(content=None):
    return patch("episodes.sync.requests.get", return_value=FakeResponse(content or load_fixture()))


def set_floor(value):
    Settings.objects.update_or_create(key="min_episode_number", defaults={"value_json": value})
    cache.clear()


class SyncTestCase(TestCase):
    """get_setting() caches for 60s in a process-wide locmem cache, which
    outlives the per-test transaction rollback. Without this, a test that
    changes the episode floor leaks that floor into every test that runs after
    it in the same process."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)


class SyncSuccessTests(SyncTestCase):
    def test_syncs_episodes_at_or_above_the_floor(self):
        with feed_ok():
            run = sync_feed(FEED_URL)

        self.assertEqual(run.status, FeedSyncRun.Status.SUCCESS)
        self.assertEqual(
            sorted(Episode.objects.values_list("episode_number", flat=True), reverse=True),
            [1896, 1895, 1890],
        )
        self.assertEqual(run.episodes_created, 3)
        self.assertEqual(run.items_below_floor, 2)  # 1889 and 1887
        self.assertEqual(run.items_failed, 1)  # the numberless item

    def test_episode_1889_is_absent_and_1890_is_the_oldest(self):
        # 1889 is the producer tribute to John and sits outside the guest-host
        # format this site exists to support (spec 3.4).
        with feed_ok():
            sync_feed(FEED_URL)
        self.assertFalse(Episode.objects.filter(episode_number=1889).exists())
        self.assertEqual(Episode.objects.order_by("published_at").first().episode_number, 1890)

    def test_running_twice_creates_no_duplicates(self):
        with feed_ok():
            sync_feed(FEED_URL)
            second = sync_feed(FEED_URL)

        self.assertEqual(Episode.objects.count(), 3)
        self.assertEqual(second.episodes_created, 0)
        self.assertEqual(second.episodes_updated, 3)

    def test_guid_variants_resolve_to_the_same_row(self):
        with feed_ok():
            sync_feed(FEED_URL)
        count = Episode.objects.count()

        # Same feed, republished over https with trailing slashes -- the shape
        # of change that would otherwise duplicate the whole catalogue.
        rewritten = load_fixture().replace(b"http://189", b"https://189").replace(
            b".noagendanotes.com<", b".noagendanotes.com/<"
        )
        with feed_ok(rewritten):
            run = sync_feed(FEED_URL)

        self.assertEqual(Episode.objects.count(), count)
        self.assertEqual(run.episodes_created, 0)

    def test_description_blob_is_never_stored(self):
        with feed_ok():
            sync_feed(FEED_URL)
        for episode in Episode.objects.all():
            for value in episode.__dict__.values():
                self.assertNotIn("Executive Producers", str(value))

    def test_guest_hosts_are_stored_from_the_feed(self):
        with feed_ok():
            sync_feed(FEED_URL)
        self.assertEqual(Episode.objects.get(episode_number=1896).feed_guest_hosts, ["Rob Dew"])
        self.assertEqual(Episode.objects.get(episode_number=1895).feed_guest_hosts, [])

    def test_updates_overwrite_changed_fields(self):
        with feed_ok():
            sync_feed(FEED_URL)
        retitled = load_fixture().replace(b'1896 - "Just Dew It"', b'1896 - "Just Dew It (Corrected)"')
        with feed_ok(retitled):
            sync_feed(FEED_URL)
        self.assertEqual(
            Episode.objects.get(episode_number=1896).title_display, "Just Dew It (Corrected)"
        )


class EpisodeFloorTests(SyncTestCase):
    def test_lowering_the_floor_backfills_on_the_next_sync(self):
        with feed_ok():
            sync_feed(FEED_URL)
        self.assertEqual(Episode.objects.count(), 3)

        set_floor(1880)
        with feed_ok():
            run = sync_feed(FEED_URL)

        self.assertEqual(run.episodes_created, 2)  # 1889 and 1887 backfilled
        self.assertTrue(Episode.objects.filter(episode_number=1889).exists())

    def test_raising_the_floor_does_not_delete_rows(self):
        set_floor(1880)
        with feed_ok():
            sync_feed(FEED_URL)
        self.assertEqual(Episode.objects.count(), 5)

        set_floor(1895)
        with feed_ok():
            run = sync_feed(FEED_URL)

        self.assertEqual(run.status, FeedSyncRun.Status.SUCCESS)
        # Nothing is deleted -- the floor governs ingestion, and hiding stored
        # episodes from public view is a separate, non-destructive concern.
        self.assertEqual(Episode.objects.count(), 5)


class SyncFailureTests(SyncTestCase):
    def setUp(self):
        super().setUp()
        with feed_ok():
            sync_feed(FEED_URL)
        self.baseline = list(Episode.objects.values_list("guid", "title_display"))

    def assert_data_intact(self):
        self.assertEqual(list(Episode.objects.values_list("guid", "title_display")), self.baseline)

    def test_connection_error_leaves_data_intact(self):
        with patch("episodes.sync.requests.get", side_effect=requests.ConnectionError("boom")):
            run = sync_feed(FEED_URL)
        self.assertEqual(run.status, FeedSyncRun.Status.FAILED)
        self.assert_data_intact()

    def test_http_error_leaves_data_intact(self):
        with patch("episodes.sync.requests.get", return_value=FakeResponse(b"nope", 503)):
            run = sync_feed(FEED_URL)
        self.assertEqual(run.status, FeedSyncRun.Status.FAILED)
        self.assertIn("503", run.error)
        self.assert_data_intact()

    def test_malformed_xml_leaves_data_intact(self):
        with patch("episodes.sync.requests.get", return_value=FakeResponse(b"<rss><channel")):
            run = sync_feed(FEED_URL)
        self.assertEqual(run.status, FeedSyncRun.Status.FAILED)
        self.assert_data_intact()

    def test_empty_feed_is_a_failure_not_a_deletion(self):
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>No Agenda</title></channel></rss>'
        with patch("episodes.sync.requests.get", return_value=FakeResponse(empty)):
            run = sync_feed(FEED_URL)
        self.assertEqual(run.status, FeedSyncRun.Status.FAILED)
        self.assertIn("zero episodes", run.error)
        self.assert_data_intact()

    def test_alerts_at_three_consecutive_failures(self):
        with patch("episodes.sync.requests.get", side_effect=requests.Timeout("slow")):
            with self.assertLogs("episodes.sync", level="WARNING") as logs:
                for _ in range(ALERT_AFTER_CONSECUTIVE_FAILURES):
                    sync_feed(FEED_URL)

        self.assertEqual(FeedSyncRun.consecutive_failures(), ALERT_AFTER_CONSECUTIVE_FAILURES)
        levels = [record.levelname for record in logs.records]
        self.assertEqual(levels[-1], "ERROR")
        self.assertNotIn("ERROR", levels[:-1])

    def test_a_success_resets_the_failure_count(self):
        with patch("episodes.sync.requests.get", side_effect=requests.Timeout("slow")):
            sync_feed(FEED_URL)
            sync_feed(FEED_URL)
        self.assertEqual(FeedSyncRun.consecutive_failures(), 2)

        with feed_ok():
            sync_feed(FEED_URL)
        self.assertEqual(FeedSyncRun.consecutive_failures(), 0)


class DryRunTests(SyncTestCase):
    def test_dry_run_writes_nothing(self):
        with feed_ok():
            run = sync_feed(FEED_URL, dry_run=True)

        self.assertEqual(run.episodes_created, 3)
        self.assertEqual(Episode.objects.count(), 0)
        self.assertEqual(FeedSyncRun.objects.count(), 0)


class ManagementCommandTests(SyncTestCase):
    def test_command_syncs(self):
        with feed_ok():
            call_command("rss_sync", url=FEED_URL)
        self.assertEqual(Episode.objects.count(), 3)

    def test_command_exits_nonzero_on_failure(self):
        with patch("episodes.sync.requests.get", side_effect=requests.ConnectionError("boom")):
            with self.assertRaises(CommandError):
                call_command("rss_sync", url=FEED_URL)
