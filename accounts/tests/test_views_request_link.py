from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class RequestMagicLinkTests(TestCase):
    def test_get_shows_form(self):
        response = self.client.get(reverse("accounts:request_link"))
        self.assertEqual(response.status_code, 200)

    def test_post_new_email_creates_user_and_sends_link(self):
        response = self.client.post(reverse("accounts:request_link"), {"email": "new@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/link_sent.html")
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("new@example.com", mail.outbox[0].to)

    def test_post_existing_email_does_not_duplicate_user(self):
        User.objects.create_user(email="existing@example.com")
        self.client.post(reverse("accounts:request_link"), {"email": "existing@example.com"})
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_response_identical_for_existing_and_nonexistent_email(self):
        User.objects.create_user(email="existing2@example.com")
        response_existing = self.client.post(reverse("accounts:request_link"), {"email": "existing2@example.com"})
        response_new = self.client.post(reverse("accounts:request_link"), {"email": "brandnew@example.com"})
        self.assertEqual(response_existing.status_code, response_new.status_code)
        self.assertEqual(
            response_existing.content.decode(),
            response_new.content.decode(),
        )

    def test_email_over_rate_limit_sends_no_further_mail(self):
        User.objects.create_user(email="throttled@example.com")
        for _ in range(3):
            self.client.post(reverse("accounts:request_link"), {"email": "throttled@example.com"})
        mail.outbox.clear()
        response = self.client.post(reverse("accounts:request_link"), {"email": "throttled@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_is_normalized_to_lowercase(self):
        self.client.post(reverse("accounts:request_link"), {"email": "MixedCase@Example.com"})
        self.assertTrue(User.objects.filter(email="mixedcase@example.com").exists())

    def test_get_client_ip_prefers_cf_connecting_ip_over_remote_addr(self):
        from django.test import RequestFactory

        from accounts.utils import get_client_ip

        factory = RequestFactory()
        request = factory.post("/login/", HTTP_CF_CONNECTING_IP="9.9.9.9", HTTP_X_FORWARDED_FOR="1.2.3.4")
        self.assertEqual(get_client_ip(request), "9.9.9.9")

    def test_get_client_ip_ignores_client_supplied_x_forwarded_for(self):
        from django.test import RequestFactory

        from accounts.utils import get_client_ip

        factory = RequestFactory()
        request = factory.post("/login/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="5.6.7.8")
        self.assertEqual(get_client_ip(request), "5.6.7.8")

    def test_rate_limited_new_signup_does_not_leave_orphaned_user(self):
        from unittest.mock import patch

        with patch("accounts.views.ip_signup_limit_exceeded", return_value=True):
            self.client.post(reverse("accounts:request_link"), {"email": "blocked-new@example.com"})
        self.assertFalse(User.objects.filter(email="blocked-new@example.com").exists())

    def test_new_signup_via_view_has_unusable_password(self):
        self.client.post(reverse("accounts:request_link"), {"email": "pwcheck@example.com"})
        user = User.objects.get(email="pwcheck@example.com")
        self.assertFalse(user.has_usable_password())
