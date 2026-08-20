from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import MagicLink, User


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
        user = User.objects.create_user(email="throttled@example.com")
        for _ in range(3):
            self.client.post(reverse("accounts:request_link"), {"email": "throttled@example.com"})
        mail.outbox.clear()
        response = self.client.post(reverse("accounts:request_link"), {"email": "throttled@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_is_normalized_to_lowercase(self):
        self.client.post(reverse("accounts:request_link"), {"email": "MixedCase@Example.com"})
        self.assertTrue(User.objects.filter(email="mixedcase@example.com").exists())
