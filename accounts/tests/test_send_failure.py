from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class MagicLinkSendFailureTests(TestCase):
    """A refused recipient must not surface as a 500.

    Production returned one: an address Resend rejected raised out of the view
    while deliverable addresses returned 200. Besides being a crash page for
    somebody who mistyped their email, that is a differential response -- the
    account/address enumeration channel spec B.3 exists to close.
    """

    URL_NAME = "accounts:request_link"

    def _post(self, email):
        return self.client.post(reverse(self.URL_NAME), {"email": email})

    def test_send_failure_does_not_500(self):
        with patch(
            "accounts.views.send_magic_link_email", side_effect=OSError("refused")
        ):
            response = self._post("typo@gmail.con")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/link_sent.html")

    def test_failed_and_successful_sends_are_indistinguishable(self):
        with patch(
            "accounts.views.send_magic_link_email", side_effect=OSError("refused")
        ):
            failed = self._post("refused@example.com")
        succeeded = self._post("fine@example.org")
        self.assertEqual(failed.status_code, succeeded.status_code)
        self.assertEqual(failed.content.decode(), succeeded.content.decode())

    def test_failure_is_logged_for_the_operator(self):
        with patch(
            "accounts.views.send_magic_link_email", side_effect=OSError("refused")
        ):
            with self.assertLogs("accounts.views", level="ERROR") as captured:
                self._post("refused2@example.com")
        self.assertIn("magic link email failed to send", "\n".join(captured.output))
        # logger.exception, so the traceback travels with it.
        self.assertIn("OSError", "\n".join(captured.output))

    def test_the_account_is_still_created_when_sending_fails(self):
        """The user can retry and get a working link; a failed send must not
        leave them unable to sign up at all."""
        with patch(
            "accounts.views.send_magic_link_email", side_effect=OSError("refused")
        ):
            self._post("retry@example.org")
        self.assertTrue(User.objects.filter(email="retry@example.org").exists())
        mail.outbox.clear()
        self._post("retry@example.org")
        self.assertEqual(len(mail.outbox), 1)

    def test_a_successful_send_still_sends(self):
        self._post("works@example.org")
        self.assertEqual(len(mail.outbox), 1)
