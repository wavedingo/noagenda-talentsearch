from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import MagicLink, User
from accounts.tokens import create_magic_link


class VerifyMagicLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def test_valid_token_logs_user_in_and_redirects_home(self):
        raw_token = create_magic_link(self.user)
        response = self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated if hasattr(response, "wsgi_request") else True)
        # Confirm the session actually authenticated the user on a follow-up request.
        home = self.client.get(reverse("core:home"))
        self.assertContains(home, "producer@example.com")

    def test_valid_token_sets_email_verified_at(self):
        raw_token = create_magic_link(self.user)
        self.assertIsNone(self.user.email_verified_at)
        self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_verified_at)

    def test_invalid_token_redirects_to_expired(self):
        response = self.client.get(reverse("accounts:verify", args=["bogus-token"]))
        self.assertRedirects(response, reverse("accounts:link_expired"))

    def test_already_used_token_redirects_to_expired(self):
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.client.logout()
        response = self.client.get(reverse("accounts:verify", args=[raw_token]))
        self.assertRedirects(response, reverse("accounts:link_expired"))

    def test_expired_link_page_does_not_prefill_email(self):
        response = self.client.get(reverse("accounts:link_expired"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "producer@example.com")
