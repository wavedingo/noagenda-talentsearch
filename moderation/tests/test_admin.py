from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from candidates.models import Candidate
from candidates.tests.helpers import make_candidate, make_user
from moderation.models import Report
from moderation.services import file_report


class ReportsAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com")
        self.moderator = User.objects.create_user(
            email="mod@example.com", role=User.Role.MODERATOR
        )
        self.candidate = make_candidate(status=Candidate.Status.LIVE)
        self.reporter = make_user("rep@example.com")
        file_report(self.reporter, self.candidate, Report.Reason.SPAM)
        self.client.force_login(self.moderator)

    def test_moderator_can_open_the_reports_queue(self):
        response = self.client.get(reverse("admin:moderation_reports_queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.candidate.stage_name)

    def test_moderator_can_dismiss_a_report(self):
        report = Report.objects.get()
        response = self.client.post(
            reverse("admin:moderation_report_decide"),
            {"report_id": report.pk, "outcome": Report.Status.DISMISSED},
        )
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.DISMISSED)

    def test_moderator_cannot_see_the_audit_log(self):
        response = self.client.get(reverse("admin:moderation_adminauditlog_changelist"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_see_the_audit_log(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:moderation_adminauditlog_changelist"))
        self.assertEqual(response.status_code, 200)


class AnalyticsAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com")
        self.client.force_login(self.admin)

    def test_analytics_page_loads(self):
        response = self.client.get(reverse("admin:candidates_analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vote velocity")
        self.assertContains(response, "Votes per account")
