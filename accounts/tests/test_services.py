from django.test import TestCase

from accounts.models import User
from accounts.services import ban_user, delete_account, set_role, unban_user
from candidates.models import Candidate
from candidates.tests.helpers import make_candidate, make_user
from moderation.models import AdminAuditLog


class BanTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com")
        self.candidate = make_candidate(status=Candidate.Status.LIVE, stage_name="Bad Actor")
        self.user = self.candidate.user

    def test_ban_sets_account_and_candidate(self):
        ban_user(self.user, self.admin)
        self.user.refresh_from_db()
        self.candidate.refresh_from_db()
        self.assertIsNotNone(self.user.banned_at)
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.candidate.status, Candidate.Status.BANNED)
        self.assertTrue(AdminAuditLog.objects.filter(action="user.ban").exists())

    def test_unban_withdraws_the_profile(self):
        ban_user(self.user, self.admin)
        unban_user(self.user, self.admin)
        self.user.refresh_from_db()
        self.candidate.refresh_from_db()
        self.assertIsNone(self.user.banned_at)
        self.assertEqual(self.candidate.status, Candidate.Status.WITHDRAWN)

    def test_role_change_is_audited(self):
        set_role(self.user, User.Role.MODERATOR, self.admin)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.MODERATOR)
        self.assertTrue(AdminAuditLog.objects.filter(action="user.role_change").exists())


class DeleteAccountTests(TestCase):
    def test_deleting_an_account_withdraws_the_candidate(self):
        candidate = make_candidate(status=Candidate.Status.LIVE)
        user = candidate.user
        delete_account(user)
        candidate.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(candidate.status, Candidate.Status.WITHDRAWN)
        self.assertIsNotNone(user.deleted_at)
        self.assertTrue(user.email.startswith("deleted-"))
