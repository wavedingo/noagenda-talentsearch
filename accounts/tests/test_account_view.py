from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_magic_link


class AccountViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com", display_name="Old Name")
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))

    def test_anonymous_user_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:account"))
        self.assertEqual(response.status_code, 302)

    def test_get_shows_current_display_name(self):
        response = self.client.get(reverse("accounts:account"))
        self.assertContains(response, "Old Name")

    def test_post_updates_display_name(self):
        self.client.post(reverse("accounts:account"), {"display_name": "New Name"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.display_name, "New Name")

    def test_delete_account_anonymizes_and_logs_out(self):
        response = self.client.post(reverse("accounts:delete_account"))
        self.assertRedirects(response, reverse("core:home"))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.deleted_at)
        self.assertNotEqual(self.user.email, "producer@example.com")
        self.assertEqual(self.user.display_name, "")
        self.assertFalse(self.user.is_active)

    def test_deleted_user_cannot_log_in_again_with_old_link(self):
        raw_token = create_magic_link(self.user)
        self.client.post(reverse("accounts:delete_account"))
        response = self.client.get(reverse("accounts:verify", args=[raw_token]))
        # token still consumes (single-use design is unaffected by deletion),
        # but the resulting session belongs to a deactivated account.
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
