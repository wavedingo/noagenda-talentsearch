from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User
from candidates.models import Candidate, Demo, RejectionReason


class CandidateModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="candidate@example.com")

    def _candidate(self, slug="the-contender", **extra):
        return Candidate.objects.create(
            user=extra.pop("user", self.user), slug=slug, stage_name="The Contender", **extra
        )

    def test_create_candidate_defaults_to_pending(self):
        candidate = self._candidate()
        self.assertEqual(candidate.status, Candidate.Status.PENDING)
        self.assertFalse(candidate.is_featured)
        self.assertFalse(candidate.is_public)
        self.assertFalse(candidate.has_pending_edit)

    def test_one_candidate_per_user(self):
        self._candidate(slug="first")
        with self.assertRaises(IntegrityError):
            self._candidate(slug="second")

    def test_slugs_are_unique(self):
        other = User.objects.create_user(email="other@example.com")
        self._candidate(slug="taken")
        with self.assertRaises(IntegrityError):
            self._candidate(slug="taken", user=other)

    def test_rejection_message_uses_the_canned_text(self):
        candidate = self._candidate(rejection_reason=RejectionReason.AUDIO_QUALITY)
        self.assertIn("clear enough listen", candidate.rejection_message)

    def test_rejection_message_appends_the_note(self):
        candidate = self._candidate(
            rejection_reason=RejectionReason.OTHER, rejection_note="Ring us."
        )
        self.assertTrue(candidate.rejection_message.endswith("Ring us."))

    def test_no_rejection_means_no_message(self):
        self.assertEqual(self._candidate().rejection_message, "")


class DemoModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(email="candidate@example.com")
        self.candidate = Candidate.objects.create(
            user=user, slug="the-contender", stage_name="The Contender"
        )

    def _demo(self, path="private/demos/a/original.mp3", **extra):
        return Demo.objects.create(candidate=self.candidate, original_path=path, **extra)

    def test_create_demo_defaults_to_pending_and_queued(self):
        demo = self._demo()
        self.assertEqual(demo.status, Demo.Status.PENDING)
        self.assertEqual(demo.processing_state, Demo.ProcessingState.QUEUED)
        self.assertFalse(demo.is_playable)
        self.assertFalse(demo.is_public)

    def test_a_demo_is_public_only_when_both_live_and_ready(self):
        demo = self._demo(
            status=Demo.Status.LIVE,
            processing_state=Demo.ProcessingState.READY,
            stream_path="public/demos/a/stream.mp3",
        )
        self.assertTrue(demo.is_public)

        demo.processing_state = Demo.ProcessingState.FAILED
        self.assertFalse(demo.is_public)

    def test_a_ready_demo_with_no_stream_path_is_not_playable(self):
        demo = self._demo(processing_state=Demo.ProcessingState.READY)
        self.assertFalse(demo.is_playable)

    def test_candidate_can_have_multiple_demos(self):
        self._demo(path="private/demos/a/original.mp3", status=Demo.Status.ARCHIVED)
        self._demo(path="private/demos/b/original.mp3")
        self.assertEqual(self.candidate.demos.count(), 2)

    def test_live_demo_ignores_archived_and_pending_ones(self):
        self._demo(path="private/demos/a/original.mp3", status=Demo.Status.ARCHIVED)
        live = self._demo(path="private/demos/b/original.mp3", status=Demo.Status.LIVE)
        self._demo(path="private/demos/c/original.mp3", status=Demo.Status.REJECTED)
        self.assertEqual(self.candidate.live_demo.pk, live.pk)

    def test_duration_display(self):
        self.assertEqual(self._demo(duration_sec=605).duration_display, "10:05")
        self.assertEqual(self._demo(path="x").duration_display, "")
