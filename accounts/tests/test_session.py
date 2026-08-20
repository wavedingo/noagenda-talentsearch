from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.tokens import create_magic_link


class SessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def _login(self):
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))

    def test_session_cookie_age_is_90_days(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60 * 24 * 90)

    def test_session_saved_every_request_for_sliding_expiry(self):
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_logout_clears_session_server_side(self):
        self._login()
        session_key = self.client.session.session_key
        self.client.post(reverse("accounts:logout"))
        from django.contrib.sessions.models import Session

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_logout_redirects_home(self):
        self._login()
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
