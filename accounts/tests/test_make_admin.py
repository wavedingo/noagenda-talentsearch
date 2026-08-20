from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from moderation.models import AdminAuditLog


class MakeAdminCommandTests(TestCase):
    def test_promotes_existing_user_to_admin(self):
        User.objects.create_user(email="existing@example.com")
        call_command("make_admin", "existing@example.com", stdout=StringIO())
        user = User.objects.get(email="existing@example.com")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_superuser)

    def test_creates_new_user_if_email_unknown(self):
        call_command("make_admin", "brandnew@example.com", stdout=StringIO())
        user = User.objects.get(email="brandnew@example.com")
        self.assertEqual(user.role, User.Role.ADMIN)

    def test_writes_audit_log_entry(self):
        call_command("make_admin", "audited@example.com", stdout=StringIO())
        user = User.objects.get(email="audited@example.com")
        entry = AdminAuditLog.objects.get(target_type="user", target_id=user.id)
        self.assertEqual(entry.action, "make_admin")

    def test_email_is_normalized(self):
        call_command("make_admin", "MixedCase@Example.com", stdout=StringIO())
        self.assertTrue(User.objects.filter(email="mixedcase@example.com").exists())
