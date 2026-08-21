from django.core import mail
from django.core.files.storage import default_storage

from candidates import services
from candidates.audio import DemoValidationError
from candidates.models import Candidate, Demo, RejectionReason
from candidates.tests.helpers import (
    MediaTestCase,
    make_candidate,
    make_mp3,
    make_user,
    photo_upload,
    set_runtime_setting,
    upload_from,
)
from moderation.models import AdminAuditLog


class SlugTests(MediaTestCase):
    def test_slug_is_derived_from_the_stage_name(self):
        candidate = services.save_profile(make_user(), "Big Sister Mo", "")
        self.assertEqual(candidate.slug, "big-sister-mo")

    def test_duplicate_stage_names_get_distinct_slugs(self):
        first = services.save_profile(make_user("a@example.com"), "The Contender", "")
        second = services.save_profile(make_user("b@example.com"), "The Contender", "")
        self.assertEqual(first.slug, "the-contender")
        self.assertEqual(second.slug, "the-contender-2")

    def test_a_stage_name_with_no_slug_characters_still_gets_one(self):
        candidate = services.save_profile(make_user(), "!!!", "")
        self.assertEqual(candidate.slug, "candidate")

    def test_slug_does_not_change_when_the_stage_name_does(self):
        """This is a URL people paste around; a rename must not break it."""
        candidate = services.save_profile(make_user(), "First Name", "")
        services.approve_candidate(candidate, actor=None)
        services.save_profile(candidate.user, "Completely Different", "")
        candidate.refresh_from_db()
        self.assertEqual(candidate.slug, "first-name")


class PreModerationTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = services.save_profile(make_user(), "The Contender", "Original bio.")
        services.approve_candidate(self.candidate, actor=None)
        self.candidate.refresh_from_db()

    def test_a_live_candidates_edit_does_not_change_the_public_copy(self):
        services.save_profile(self.candidate.user, "New Name", "Rewritten bio.")
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.stage_name, "The Contender")
        self.assertEqual(self.candidate.bio, "Original bio.")
        self.assertEqual(self.candidate.pending_bio, "Rewritten bio.")
        self.assertTrue(self.candidate.has_pending_edit)

    def test_editing_does_not_take_a_live_profile_off_the_site(self):
        services.save_profile(self.candidate.user, "New Name", "Rewritten bio.")
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.Status.LIVE)

    def test_approving_an_edit_promotes_it(self):
        services.save_profile(self.candidate.user, "New Name", "Rewritten bio.")
        self.candidate.refresh_from_db()

        services.approve_profile_edit(self.candidate, actor=None)
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.stage_name, "New Name")
        self.assertEqual(self.candidate.bio, "Rewritten bio.")
        self.assertFalse(self.candidate.has_pending_edit)

    def test_rejecting_an_edit_discards_it_and_leaves_the_profile_live(self):
        services.save_profile(self.candidate.user, "New Name", "Rewritten bio.")
        self.candidate.refresh_from_db()

        services.reject_profile_edit(self.candidate, None, RejectionReason.HOUSE_RULES)
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.status, Candidate.Status.LIVE)
        self.assertEqual(self.candidate.bio, "Original bio.")
        self.assertFalse(self.candidate.has_pending_edit)

    def test_a_rejected_candidate_edits_the_main_fields_and_returns_to_pending(self):
        services.reject_candidate(self.candidate, None, RejectionReason.AUDIO_QUALITY)
        self.candidate.refresh_from_db()

        services.save_profile(self.candidate.user, "Second Try", "Better bio.")
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.status, Candidate.Status.PENDING)
        self.assertEqual(self.candidate.bio, "Better bio.")
        self.assertFalse(self.candidate.has_pending_edit)
        self.assertEqual(self.candidate.rejection_reason, "")


class PhotoTests(MediaTestCase):
    def test_a_saved_photo_is_stored_and_reachable(self):
        candidate = services.save_profile(make_user(), "Snapper", "", photo_file=photo_upload())
        self.assertTrue(candidate.photo_path.startswith("public/photos/"))
        self.assertTrue(default_storage.exists(candidate.photo_path))
        self.assertTrue(candidate.photo_url)

    def test_a_live_candidates_new_photo_waits_for_approval(self):
        candidate = services.save_profile(make_user(), "Snapper", "", photo_file=photo_upload())
        services.approve_candidate(candidate, actor=None)
        candidate.refresh_from_db()
        approved_path = candidate.photo_path

        services.save_profile(candidate.user, "Snapper", "", photo_file=photo_upload())
        candidate.refresh_from_db()

        self.assertEqual(candidate.photo_path, approved_path)
        self.assertNotEqual(candidate.pending_photo_path, "")


class SubmitDemoTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate()

    def _upload(self, seconds=2, name="demo.mp3"):
        path = make_mp3(self.work_path(name), seconds=seconds)
        return upload_from(path, name=name)

    def test_a_valid_upload_is_stored_and_queued(self):
        demo = services.submit_demo(self.candidate, self._upload())

        self.assertEqual(demo.status, Demo.Status.PENDING)
        self.assertEqual(demo.processing_state, Demo.ProcessingState.QUEUED)
        self.assertTrue(demo.original_path.startswith("private/demos/"))
        self.assertTrue(default_storage.exists(demo.original_path))
        self.assertEqual(demo.stream_path, "")

    def test_the_original_is_never_stored_under_the_public_prefix(self):
        demo = services.submit_demo(self.candidate, self._upload())
        self.assertNotIn("public/", demo.original_path)

    def test_a_new_demo_archives_the_previous_one(self):
        """Spec 3.2: a new demo is a new rating slate."""
        first = services.submit_demo(self.candidate, self._upload(name="first.mp3"))
        second = services.submit_demo(self.candidate, self._upload(name="second.mp3"))

        first.refresh_from_db()
        self.assertEqual(first.status, Demo.Status.ARCHIVED)
        self.assertEqual(second.status, Demo.Status.PENDING)
        self.assertEqual(self.candidate.current_demo.pk, second.pk)

    def test_ratings_stay_attached_to_the_archived_demo(self):
        from ratings.models import Rating

        first = services.submit_demo(self.candidate, self._upload(name="first.mp3"))
        rating = Rating.objects.create(
            user=make_user("voter@example.com"),
            rateable_type=Rating.RateableType.DEMO,
            rateable_id=first.pk,
            stars=5,
        )
        services.submit_demo(self.candidate, self._upload(name="second.mp3"))

        rating.refresh_from_db()
        self.assertEqual(rating.rateable_id, first.pk)

    def test_rejects_a_file_over_the_size_limit(self):
        set_runtime_setting("demo_max_file_mb", 0)
        with self.assertRaises(DemoValidationError) as caught:
            services.submit_demo(self.candidate, self._upload())
        self.assertIn("limit is 0 MB", str(caught.exception))

    def test_rejects_a_file_over_the_duration_limit(self):
        set_runtime_setting("demo_max_duration_sec", 1)
        with self.assertRaises(DemoValidationError):
            services.submit_demo(self.candidate, self._upload(seconds=5))

    def test_rejects_a_non_mp3_extension_before_touching_ffmpeg(self):
        with self.assertRaises(DemoValidationError) as caught:
            services.submit_demo(self.candidate, self._upload(name="demo.wav"))
        self.assertIn("MP3", str(caught.exception))

    def test_nothing_is_stored_when_validation_fails(self):
        set_runtime_setting("demo_max_duration_sec", 1)
        with self.assertRaises(DemoValidationError):
            services.submit_demo(self.candidate, self._upload(seconds=5))
        self.assertEqual(self.candidate.demos.count(), 0)

    def test_enforces_a_daily_upload_quota(self):
        for index in range(services.MAX_DEMO_UPLOADS_PER_DAY):
            services.submit_demo(self.candidate, self._upload(name=f"demo{index}.mp3"))

        with self.assertRaises(DemoValidationError) as caught:
            services.submit_demo(self.candidate, self._upload(name="one-too-many.mp3"))
        self.assertIn("daily limit", str(caught.exception))


class ModerationOutcomeTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate()
        self.moderator = make_user("mod@example.com")

    def test_approving_a_candidate_emails_them_and_records_an_audit_entry(self):
        services.approve_candidate(self.candidate, self.moderator)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.candidate.slug, mail.outbox[0].body)
        entry = AdminAuditLog.objects.get()
        self.assertEqual(entry.action, "candidate.approve")
        self.assertEqual(entry.admin_user, self.moderator)

    def test_rejecting_a_candidate_sends_the_canned_reason(self):
        services.reject_candidate(self.candidate, self.moderator, RejectionReason.AUDIO_QUALITY)

        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.Status.REJECTED)
        self.assertIn("clear enough listen", mail.outbox[0].body)

    def test_a_rejection_note_is_appended_to_the_canned_reason(self):
        services.reject_candidate(
            self.candidate, self.moderator, RejectionReason.OTHER, note="Try recording indoors."
        )
        self.assertIn("Try recording indoors.", mail.outbox[0].body)

    def test_reopening_a_withdrawn_profile_returns_it_to_pending_not_live(self):
        services.approve_candidate(self.candidate, self.moderator)
        services.withdraw(self.candidate)
        services.reopen(self.candidate)

        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.Status.PENDING)
