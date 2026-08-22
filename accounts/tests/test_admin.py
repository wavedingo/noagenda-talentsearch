from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from candidates.models import Candidate
from candidates.tests.helpers import make_candidate


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com")
        self.moderator = User.objects.create_user(
            email="mod@example.com", role=User.Role.MODERATOR
        )
        self.candidate = make_candidate(status=Candidate.Status.LIVE)
        self.client.force_login(self.admin)

    def test_admin_can_ban_from_the_user_page(self):
        url = reverse("admin:accounts_user_action", args=[self.candidate.user_id])
        response = self.client.post(url, {"action": "ban"})
        self.assertEqual(response.status_code, 302)
        self.candidate.user.refresh_from_db()
        self.candidate.refresh_from_db()
        self.assertIsNotNone(self.candidate.user.banned_at)
        self.assertEqual(self.candidate.status, Candidate.Status.BANNED)

    def test_moderator_cannot_ban(self):
        self.client.force_login(self.moderator)
        url = reverse("admin:accounts_user_action", args=[self.candidate.user_id])
        self.client.post(url, {"action": "ban"})
        self.candidate.user.refresh_from_db()
        self.assertIsNone(self.candidate.user.banned_at)
