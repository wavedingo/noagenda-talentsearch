from django.test import TestCase
from django.urls import reverse

from candidates.models import Candidate
from candidates.tests.helpers import make_candidate, make_user
from moderation.models import Report
from moderation.services import AUTO_HIDE_THRESHOLD, ReportError, file_report, resolve_report


class ReportServiceTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate(status=Candidate.Status.LIVE, stage_name="The Contender")
        self.reporter = make_user("reporter@example.com")

    def test_files_an_open_report(self):
        report, created = file_report(self.reporter, self.candidate, Report.Reason.SPAM, "bot")
        self.assertTrue(created)
        self.assertEqual(report.status, Report.Status.OPEN)
        self.assertEqual(report.target_id, self.candidate.pk)

    def test_a_second_report_from_the_same_account_updates(self):
        file_report(self.reporter, self.candidate, Report.Reason.SPAM)
        report, created = file_report(self.reporter, self.candidate, Report.Reason.OFFENSIVE, "worse")
        self.assertFalse(created)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(report.reason, Report.Reason.OFFENSIVE)
        self.assertEqual(report.details, "worse")

    def test_cannot_report_own_profile(self):
        with self.assertRaises(ReportError):
            file_report(self.candidate.user, self.candidate, Report.Reason.SPAM)

    def test_ten_unique_open_reports_hide_the_profile(self):
        for i in range(AUTO_HIDE_THRESHOLD):
            file_report(make_user(f"r{i}@example.com"), self.candidate, Report.Reason.SPAM)
        self.candidate.refresh_from_db()
        self.assertIsNotNone(self.candidate.hidden_at)
        self.assertFalse(self.candidate.is_public)

    def test_dropping_below_threshold_unhides(self):
        reports = []
        for i in range(AUTO_HIDE_THRESHOLD):
            report, _ = file_report(make_user(f"r{i}@example.com"), self.candidate, Report.Reason.SPAM)
            reports.append(report)
        self.candidate.refresh_from_db()
        self.assertIsNotNone(self.candidate.hidden_at)
        resolve_report(reports[0], self.reporter, Report.Status.DISMISSED)
        self.candidate.refresh_from_db()
        self.assertIsNone(self.candidate.hidden_at)
        self.assertTrue(self.candidate.is_public)


class ReportViewTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate(status=Candidate.Status.LIVE, stage_name="The Contender")
        self.reporter = make_user("reporter@example.com")

    def test_anonymous_visitors_are_sent_to_login(self):
        response = self.client.get(reverse("candidates:report", args=[self.candidate.slug]))
        self.assertEqual(response.status_code, 302)

    def test_producer_can_file_a_report(self):
        self.client.force_login(self.reporter)
        response = self.client.post(
            reverse("candidates:report", args=[self.candidate.slug]),
            {"reason": Report.Reason.SPAM, "details": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Report.objects.filter(reporter=self.reporter, target_id=self.candidate.pk).exists()
        )

    def test_hidden_candidate_is_omitted_from_the_public_list(self):
        for i in range(AUTO_HIDE_THRESHOLD):
            file_report(make_user(f"h{i}@example.com"), self.candidate, Report.Reason.SPAM)
        response = self.client.get(reverse("candidates:list"))
        self.assertNotContains(response, "The Contender")
        detail = self.client.get(reverse("candidates:detail", args=[self.candidate.slug]))
        self.assertEqual(detail.status_code, 404)
