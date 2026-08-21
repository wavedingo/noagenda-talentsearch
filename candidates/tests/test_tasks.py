"""Queue mechanics.

The point of these is that the *table* is the durability story: whatever happens
to the thread, a demo ends up either ready or back on the queue, never lost and
never processed twice.
"""

import os
import tempfile
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from candidates import services, tasks
from candidates.audio import TranscodeError, probe
from candidates.models import Demo
from candidates.tests.helpers import MediaTestCase, make_candidate, make_mp3, upload_from


class ProcessDemoTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate()
        self.demo = self._submit()

    def _submit(self, name="demo.mp3", seconds=3):
        upload = upload_from(make_mp3(self.work_path(name), seconds=seconds), name=name)
        return services.submit_demo(self.candidate, upload)

    def test_processing_produces_a_ready_streaming_copy(self):
        tasks.process_demo(self.demo.pk)
        self.demo.refresh_from_db()

        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.READY)
        self.assertTrue(self.demo.stream_path.startswith("public/demos/"))
        self.assertTrue(default_storage.exists(self.demo.stream_path))
        self.assertIsNotNone(self.demo.processed_at)

    def test_the_streaming_copy_is_a_128kbps_mp3(self):
        tasks.process_demo(self.demo.pk)
        self.demo.refresh_from_db()

        with tasks.storage.local_copy(self.demo.stream_path) as local:
            data = probe(local)
        self.assertIn("mp3", data["format"]["format_name"].split(","))
        self.assertAlmostEqual(int(data["format"]["bit_rate"]), 128_000, delta=8_000)

    def test_claiming_is_atomic(self):
        """A second worker on a demo already claimed does nothing at all."""
        self.assertTrue(tasks.claim(self.demo.pk))
        self.assertFalse(tasks.claim(self.demo.pk))
        self.assertIsNone(tasks.process_demo(self.demo.pk))

    def test_a_failed_transcode_records_the_error_and_stays_unplayable(self):
        with mock.patch(
            "candidates.tasks.transcode_to_stream", side_effect=TranscodeError("ffmpeg failed: nope")
        ):
            tasks.process_demo(self.demo.pk)
        self.demo.refresh_from_db()

        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.FAILED)
        self.assertIn("nope", self.demo.processing_error)
        self.assertFalse(self.demo.is_playable)
        self.assertFalse(self.demo.is_public)

    def test_a_missing_original_fails_the_demo_rather_than_raising(self):
        default_storage.delete(self.demo.original_path)
        tasks.process_demo(self.demo.pk)
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.FAILED)


class ReclaimTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate()
        upload = upload_from(make_mp3(self.work_path("demo.mp3"), seconds=2))
        self.demo = services.submit_demo(self.candidate, upload)

    def test_a_demo_abandoned_mid_transcode_goes_back_on_the_queue(self):
        tasks.claim(self.demo.pk)
        Demo.objects.filter(pk=self.demo.pk).update(
            processing_started_at=timezone.now() - timedelta(hours=2)
        )

        self.assertEqual(tasks.reclaim_stale(), 1)
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.QUEUED)

    def test_a_demo_still_transcoding_is_left_alone(self):
        tasks.claim(self.demo.pk)
        self.assertEqual(tasks.reclaim_stale(), 0)
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.PROCESSING)

    def test_drain_queue_reclaims_then_processes(self):
        tasks.claim(self.demo.pk)
        Demo.objects.filter(pk=self.demo.pk).update(
            processing_started_at=timezone.now() - timedelta(hours=2)
        )

        processed, failed = tasks.drain_queue()

        self.assertEqual((processed, failed), (1, 0))
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.READY)


class ProcessDemosCommandTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate()
        upload = upload_from(make_mp3(self.work_path("demo.mp3"), seconds=2))
        self.demo = services.submit_demo(self.candidate, upload)

    def test_command_drains_the_queue(self):
        out = StringIO()
        call_command("process_demos", stdout=out)

        self.demo.refresh_from_db()
        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.READY)
        self.assertIn("Processed 1 demo(s)", out.getvalue())

    def test_command_can_target_one_demo(self):
        out = StringIO()
        call_command("process_demos", demo_id=self.demo.pk, stdout=out)

        self.demo.refresh_from_db()
        self.assertEqual(self.demo.processing_state, Demo.ProcessingState.READY)
        self.assertIn("is ready", out.getvalue())

    def test_command_is_a_no_op_on_an_already_processed_demo(self):
        call_command("process_demos", stdout=StringIO())
        out = StringIO()
        call_command("process_demos", demo_id=self.demo.pk, stdout=out)
        self.assertIn("not queued", out.getvalue())


class DispatchTests(MediaTestCase):
    def test_background_dispatch_is_off_under_the_test_runner(self):
        """Set in config/settings.py: a thread would race the test's own
        transaction rollback."""
        from django.conf import settings

        self.assertFalse(settings.DEMO_PROCESS_IN_BACKGROUND)
        self.assertIsNone(tasks.dispatch(mock.Mock(pk=1)))


class ThreadedDispatchTests(TransactionTestCase):
    """The production path, exercised across a real thread boundary.

    TransactionTestCase rather than TestCase because a worker thread gets its
    own connection and cannot see rows held open in another connection's
    uncommitted transaction — which is also why `submit_demo` dispatches from
    `transaction.on_commit` rather than inline.
    """

    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        self._workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._workdir.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)
        cache.clear()
        self.addCleanup(cache.clear)

    def test_dispatch_transcodes_in_the_background(self):
        candidate = make_candidate()
        source = make_mp3(os.path.join(self._workdir.name, "demo.mp3"), seconds=2)
        demo = services.submit_demo(candidate, upload_from(source))

        with override_settings(DEMO_PROCESS_IN_BACKGROUND=True):
            thread = tasks.dispatch(demo)
        thread.join(timeout=120)

        demo.refresh_from_db()
        self.assertEqual(demo.processing_state, Demo.ProcessingState.READY)
        self.assertTrue(demo.is_playable)
