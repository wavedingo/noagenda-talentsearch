from django.core import mail
from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_magic_link
from candidates import services
from candidates.models import Candidate, Demo, RejectionReason
from candidates.tests.helpers import MediaTestCase, make_candidate, make_mp3, make_user, upload_from
from moderation.models import AdminAuditLog

QUEUE_URL = "/django-admin/candidates/candidate/queue/"
DECIDE_URL = "/django-admin/candidates/candidate/queue/decide/"
PROCESS_URL = "/django-admin/candidates/candidate/queue/process-demos/"


class QueueTestCase(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.moderator = make_user("mod@example.com", role=User.Role.MODERATOR)
        self.client.get(reverse("accounts:verify", args=[create_magic_link(self.moderator)]))


class QueueAccessTests(QueueTestCase):
    def test_a_producer_cannot_reach_the_queue(self):
        self.client.logout()
        producer = make_user("producer@example.com")
        self.client.get(reverse("accounts:verify", args=[create_magic_link(producer)]))

        response = self.client.get(QUEUE_URL)
        self.assertNotEqual(response.status_code, 200)

    def test_an_anonymous_visitor_cannot_reach_the_queue(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(QUEUE_URL).status_code, 200)

    def test_a_producer_cannot_approve_anyone(self):
        candidate = make_candidate()
        self.client.logout()
        producer = make_user("producer@example.com")
        self.client.get(reverse("accounts:verify", args=[create_magic_link(producer)]))

        self.client.post(
            DECIDE_URL, {"target": "candidate", "target_id": candidate.pk, "action": "approve"}
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, Candidate.Status.PENDING)


class ModeratorAccessTests(QueueTestCase):
    def test_a_moderator_sees_the_candidates_section_and_a_link_to_the_queue(self):
        """Without this a moderator logs in to an empty dashboard."""
        self.assertContains(self.client.get("/django-admin/"), "Candidates")
        self.assertContains(self.client.get("/django-admin/candidates/candidate/"), QUEUE_URL)

    def test_a_moderator_cannot_edit_candidate_records_directly(self):
        candidate = make_candidate()
        response = self.client.get(f"/django-admin/candidates/candidate/{candidate.pk}/change/")
        self.assertNotContains(response, "_save", status_code=200)


class QueueContentTests(QueueTestCase):
    def test_pending_candidates_appear(self):
        make_candidate(stage_name="Waiting Wanda")
        self.assertContains(self.client.get(QUEUE_URL), "Waiting Wanda")

    def test_live_candidates_do_not(self):
        make_candidate(stage_name="Already Live", status=Candidate.Status.LIVE)
        self.assertNotContains(self.client.get(QUEUE_URL), "Already Live")

    def test_a_demo_still_transcoding_is_not_offered_for_approval(self):
        """Moderators approve by listening; there is nothing to listen to yet."""
        candidate = make_candidate(status=Candidate.Status.LIVE)
        upload = upload_from(make_mp3(self.work_path("demo.mp3"), seconds=2))
        services.submit_demo(candidate, upload)

        response = self.client.get(QUEUE_URL)
        self.assertEqual(list(response.context["pending_demos"]), [])
        self.assertEqual(len(response.context["stuck_demos"]), 1)

    def test_a_ready_demo_is_offered_with_its_stream_url(self):
        from candidates import tasks

        candidate = make_candidate(status=Candidate.Status.LIVE)
        upload = upload_from(make_mp3(self.work_path("demo.mp3"), seconds=2))
        demo = services.submit_demo(candidate, upload)
        tasks.process_demo(demo.pk)
        demo.refresh_from_db()

        body = self.client.get(QUEUE_URL).content.decode()
        self.assertIn(demo.stream_path, body)
        self.assertNotIn(demo.original_path, body)

    def test_a_failed_demo_shows_its_error(self):
        candidate = make_candidate()
        Demo.objects.create(
            candidate=candidate,
            original_path="private/demos/x/original.mp3",
            processing_state=Demo.ProcessingState.FAILED,
            processing_error="ffmpeg failed: Invalid data found",
        )
        self.assertContains(self.client.get(QUEUE_URL), "Invalid data found")


class DecisionTests(QueueTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(stage_name="Waiting Wanda")

    def test_approving_publishes_and_emails(self):
        self.client.post(
            DECIDE_URL, {"target": "candidate", "target_id": self.candidate.pk, "action": "approve"}
        )
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.status, Candidate.Status.LIVE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(AdminAuditLog.objects.filter(action="candidate.approve").exists())

    def test_rejecting_requires_a_reason(self):
        self.client.post(
            DECIDE_URL,
            {"target": "candidate", "target_id": self.candidate.pk, "action": "reject", "reason": ""},
        )
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.status, Candidate.Status.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_rejecting_with_a_reason_emails_the_canned_text(self):
        self.client.post(
            DECIDE_URL,
            {
                "target": "candidate",
                "target_id": self.candidate.pk,
                "action": "reject",
                "reason": RejectionReason.HOUSE_RULES,
                "note": "See the About page.",
            },
        )
        self.candidate.refresh_from_db()

        self.assertEqual(self.candidate.status, Candidate.Status.REJECTED)
        self.assertIn("house rules", mail.outbox[0].body)
        self.assertIn("See the About page.", mail.outbox[0].body)

    def test_approving_a_profile_edit_promotes_the_draft(self):
        candidate = services.save_profile(make_user("editor@example.com"), "Editor", "First bio.")
        services.approve_candidate(candidate, self.moderator)
        candidate.refresh_from_db()
        services.save_profile(candidate.user, "Editor", "Second bio.")

        self.client.post(
            DECIDE_URL, {"target": "profile_edit", "target_id": candidate.pk, "action": "approve"}
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.bio, "Second bio.")

    def test_decisions_reject_get(self):
        self.assertEqual(self.client.get(DECIDE_URL).status_code, 405)

    def test_an_unknown_target_404s_rather_than_500s(self):
        response = self.client.post(
            DECIDE_URL, {"target": "candidate", "target_id": 999999, "action": "approve"}
        )
        self.assertEqual(response.status_code, 404)


class ProcessDemosButtonTests(QueueTestCase):
    def test_the_button_drains_the_queue(self):
        candidate = make_candidate(status=Candidate.Status.LIVE)
        upload = upload_from(make_mp3(self.work_path("demo.mp3"), seconds=2))
        demo = services.submit_demo(candidate, upload)

        self.client.post(PROCESS_URL)

        demo.refresh_from_db()
        self.assertEqual(demo.processing_state, Demo.ProcessingState.READY)

    def test_the_button_rejects_get(self):
        self.assertEqual(self.client.get(PROCESS_URL).status_code, 405)
