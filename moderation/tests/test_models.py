from django.test import TestCase

from accounts.models import User
from moderation.models import AdminAuditLog, Report


class ModerationModelTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(email="reporter@example.com")
        self.admin = User.objects.create_superuser(email="admin@example.com")

    def test_create_report_defaults_to_open(self):
        report = Report.objects.create(
            reporter=self.reporter, target_type="candidate", target_id=1, reason=Report.Reason.SPAM
        )
        self.assertEqual(report.status, Report.Status.OPEN)

    def test_create_audit_log_entry(self):
        entry = AdminAuditLog.objects.create(
            admin_user=self.admin,
            action="grant_role",
            target_type="user",
            target_id=self.reporter.id,
            metadata_json={"old_role": "producer", "new_role": "moderator"},
        )
        self.assertEqual(entry.metadata_json["new_role"], "moderator")

    def test_audit_log_survives_admin_user_deletion(self):
        entry = AdminAuditLog.objects.create(admin_user=self.admin, action="test", target_type="user", target_id=1)
        self.admin.delete()
        entry.refresh_from_db()
        self.assertIsNone(entry.admin_user)
