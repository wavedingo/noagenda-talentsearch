from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_magic_link
from candidates import services
from candidates.models import Candidate, Demo
from candidates.tests.helpers import (
    MediaTestCase,
    make_candidate,
    make_mp3,
    make_user,
    set_runtime_setting,
    upload_from,
)

SECRET_BIO = "Unapproved words that must not reach a public page."


class ViewTestCase(MediaTestCase):
    def log_in(self, user):
        self.client.get(reverse("accounts:verify", args=[create_magic_link(user)]))
        return user


class CandidateListTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.live = make_candidate(
            email="live@example.com", stage_name="Live One", status=Candidate.Status.LIVE
        )

    def test_lists_live_candidates(self):
        response = self.client.get(reverse("candidates:list"))
        self.assertContains(response, "Live One")

    def test_entire_candidate_card_links_to_the_profile(self):
        response = self.client.get(reverse("candidates:list"))
        detail = reverse("candidates:detail", args=[self.live.slug])
        self.assertContains(response, f'class="candidate-card-link" href="{detail}"')
        # Name is no longer a nested link — the whole card is the hit target.
        self.assertNotContains(response, f'<a href="{detail}">Live One</a>')

    def test_hides_every_other_status(self):
        for index, status in enumerate(
            [
                Candidate.Status.PENDING,
                Candidate.Status.REJECTED,
                Candidate.Status.WITHDRAWN,
                Candidate.Status.BANNED,
            ]
        ):
            make_candidate(
                email=f"hidden{index}@example.com",
                stage_name=f"Hidden {status}",
                status=status,
                bio=SECRET_BIO,
            )

        body = self.client.get(reverse("candidates:list")).content.decode()

        self.assertNotIn("Hidden", body)
        self.assertNotIn(SECRET_BIO, body)

    def test_sorts_by_name_on_request(self):
        make_candidate(email="a@example.com", stage_name="Aardvark", status=Candidate.Status.LIVE)
        body = self.client.get(reverse("candidates:list"), {"sort": "name"}).content.decode()
        self.assertLess(body.index("Aardvark"), body.index("Live One"))

    def test_an_unknown_sort_falls_back_rather_than_erroring(self):
        response = self.client.get(reverse("candidates:list"), {"sort": "; DROP TABLE"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sort"], "newest")

    def test_empty_state(self):
        Candidate.objects.all().delete()
        self.assertContains(self.client.get(reverse("candidates:list")), "No candidates yet")


class CandidateDetailTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(stage_name="The Contender", status=Candidate.Status.PENDING)

    def _url(self):
        return reverse("candidates:detail", args=[self.candidate.slug])

    def test_a_pending_profile_is_not_public(self):
        self.assertEqual(self.client.get(self._url()).status_code, 404)

    def test_a_live_profile_is_public(self):
        self.candidate.status = Candidate.Status.LIVE
        self.candidate.save()
        self.assertContains(self.client.get(self._url()), "The Contender")

    def test_an_owner_can_preview_their_own_pending_profile(self):
        self.log_in(self.candidate.user)
        response = self.client.get(self._url())
        self.assertContains(response, "The Contender")
        self.assertContains(response, "Not public")

    def test_a_moderator_can_preview_a_pending_profile(self):
        self.log_in(make_user("mod@example.com", role=User.Role.MODERATOR))
        self.assertEqual(self.client.get(self._url()).status_code, 200)

    def test_another_producer_cannot(self):
        self.log_in(make_user("nosy@example.com"))
        self.assertEqual(self.client.get(self._url()).status_code, 404)

    def test_unknown_slug_404s(self):
        self.assertEqual(self.client.get(reverse("candidates:detail", args=["nobody"])).status_code, 404)

    def test_only_a_live_demo_is_offered_for_playback(self):
        demo = Demo.objects.create(
            candidate=self.candidate,
            original_path="private/demos/x/original.mp3",
            stream_path="public/demos/x/stream.mp3",
            status=Demo.Status.PENDING,
            processing_state=Demo.ProcessingState.READY,
        )
        self.candidate.status = Candidate.Status.LIVE
        self.candidate.save()

        body = self.client.get(self._url()).content.decode()
        self.assertNotIn(demo.stream_path, body)
        self.assertIn("No demo published yet", body)

    def test_the_original_upload_is_never_linked(self):
        Demo.objects.create(
            candidate=self.candidate,
            original_path="private/demos/x/original.mp3",
            stream_path="public/demos/x/stream.mp3",
            status=Demo.Status.LIVE,
            processing_state=Demo.ProcessingState.READY,
        )
        self.candidate.status = Candidate.Status.LIVE
        self.candidate.save()

        body = self.client.get(self._url()).content.decode()
        self.assertIn("public/demos/x/stream.mp3", body)
        self.assertNotIn("private/", body)


class PreModerationOnPublicPagesTests(ViewTestCase):
    """Principle 2, asserted against rendered HTML rather than the model —
    the model being right is no comfort if a template reads the wrong field."""

    def setUp(self):
        super().setUp()
        self.candidate = services.save_profile(make_user(), "The Contender", "Approved bio.")
        services.approve_candidate(self.candidate, actor=None)
        self.candidate.refresh_from_db()
        services.save_profile(self.candidate.user, "New Name", SECRET_BIO)

    def test_a_pending_edit_is_absent_from_the_detail_page(self):
        body = self.client.get(
            reverse("candidates:detail", args=[self.candidate.slug])
        ).content.decode()
        self.assertIn("Approved bio.", body)
        self.assertNotIn(SECRET_BIO, body)
        self.assertNotIn("New Name", body)

    def test_a_pending_edit_is_absent_from_the_list_page(self):
        body = self.client.get(reverse("candidates:list")).content.decode()
        self.assertNotIn(SECRET_BIO, body)
        self.assertNotIn("New Name", body)

    def test_a_pending_edit_is_absent_from_the_home_page(self):
        body = self.client.get(reverse("core:home")).content.decode()
        self.assertNotIn(SECRET_BIO, body)
        self.assertNotIn("New Name", body)


class AuditionViewTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.log_in(make_user())

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("candidates:audition"))
        self.assertEqual(response.status_code, 302)

    def test_creates_a_profile(self):
        self.client.post(
            reverse("candidates:audition"), {"stage_name": "The Contender", "bio": "Hello."}
        )
        candidate = Candidate.objects.get(user=self.user)
        self.assertEqual(candidate.stage_name, "The Contender")
        self.assertEqual(candidate.status, Candidate.Status.PENDING)

    def test_shows_the_rejection_reason_back_to_the_candidate(self):
        candidate = services.save_profile(self.user, "The Contender", "Hello.")
        services.reject_candidate(candidate, None, "audio_quality")

        self.assertContains(self.client.get(reverse("candidates:audition")), "clear enough listen")

    def test_a_closed_audition_window_blocks_new_profiles(self):
        set_runtime_setting("auditions_open", False)
        self.client.post(reverse("candidates:audition"), {"stage_name": "Too Late", "bio": ""})
        self.assertFalse(Candidate.objects.filter(user=self.user).exists())

    def test_an_existing_candidate_can_still_edit_when_auditions_close(self):
        services.save_profile(self.user, "The Contender", "Hello.")
        set_runtime_setting("auditions_open", False)

        self.client.post(
            reverse("candidates:audition"), {"stage_name": "The Contender", "bio": "Updated."}
        )
        self.assertEqual(Candidate.objects.get(user=self.user).bio, "Updated.")

    def test_the_remove_photo_control_only_appears_when_there_is_a_photo(self):
        from candidates.tests.helpers import photo_upload

        self.assertNotContains(self.client.get(reverse("candidates:audition")), "clear_photo")

        self.client.post(
            reverse("candidates:audition"),
            {"stage_name": "The Contender", "bio": "", "photo": photo_upload()},
        )
        self.assertContains(self.client.get(reverse("candidates:audition")), "clear_photo")

    def test_a_bad_photo_is_reported_on_the_form_not_as_a_500(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(
            reverse("candidates:audition"),
            {
                "stage_name": "The Contender",
                "bio": "",
                "photo": SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "doesn&#x27;t look like an image")
        self.assertFalse(Candidate.objects.filter(user=self.user).exists())


class DemoUploadViewTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate()
        self.log_in(self.candidate.user)

    def _upload(self, name="demo.mp3", seconds=2):
        return upload_from(make_mp3(self.work_path(name), seconds=seconds), name=name)

    def test_uploading_queues_a_demo(self):
        self.client.post(reverse("candidates:upload_demo"), {"demo": self._upload()})
        demo = self.candidate.demos.get()
        self.assertEqual(demo.processing_state, Demo.ProcessingState.QUEUED)

    def test_a_rejected_upload_explains_itself_on_the_page(self):
        set_runtime_setting("demo_max_duration_sec", 1)
        response = self.client.post(
            reverse("candidates:upload_demo"), {"demo": self._upload(seconds=5)}, follow=True
        )
        self.assertContains(response, "Trim it")
        self.assertEqual(self.candidate.demos.count(), 0)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("candidates:upload_demo")).status_code, 405)

    def test_a_user_without_a_profile_is_sent_to_create_one(self):
        self.client.logout()
        self.log_in(make_user("profileless@example.com"))
        response = self.client.post(reverse("candidates:upload_demo"), {"demo": self._upload()})
        self.assertRedirects(response, reverse("candidates:audition"))
        self.assertEqual(Demo.objects.count(), 0)

    def test_a_user_cannot_upload_onto_someone_elses_profile(self):
        """There is no candidate id in the request at all — the profile is
        looked up from the session — so this is a structural guarantee."""
        other = make_candidate(email="other@example.com", stage_name="Someone Else")
        self.client.post(reverse("candidates:upload_demo"), {"demo": self._upload()})

        self.assertEqual(other.demos.count(), 0)
        self.assertEqual(self.candidate.demos.count(), 1)


class WithdrawTests(ViewTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(status=Candidate.Status.LIVE)
        self.log_in(self.candidate.user)

    def test_withdrawing_hides_the_profile(self):
        self.client.post(reverse("candidates:withdraw"))
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.Status.WITHDRAWN)
        self.assertEqual(
            self.client.get(reverse("candidates:detail", args=[self.candidate.slug])).status_code, 200
        )  # the owner can still see it
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("candidates:detail", args=[self.candidate.slug])).status_code, 404
        )

    def test_reopening_returns_to_pending(self):
        self.client.post(reverse("candidates:withdraw"))
        self.client.post(reverse("candidates:reopen"))
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.Status.PENDING)

    def test_withdraw_rejects_get(self):
        self.assertEqual(self.client.get(reverse("candidates:withdraw")).status_code, 405)


class TemplateSyntaxLeakTests(ViewTestCase):
    """Django's {# #} is single-line only; a multi-line one renders as body text."""

    def test_no_raw_template_syntax_reaches_the_page(self):
        candidate = make_candidate(status=Candidate.Status.LIVE)
        self.log_in(candidate.user)
        urls = [
            reverse("core:home"),
            reverse("candidates:list"),
            reverse("candidates:detail", args=[candidate.slug]),
            reverse("candidates:audition"),
        ]
        for url in urls:
            body = self.client.get(url).content.decode()
            for token in ("{#", "#}", "{%", "%}"):
                self.assertNotIn(token, body, f"{token} leaked into {url}")
