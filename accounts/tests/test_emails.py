from email.utils import parseaddr

from django.core import mail
from django.test import TestCase, override_settings

from accounts.emails import send_magic_link_email


@override_settings(APP_URL="https://noagendatalentsearch.com")
class MagicLinkEmailTests(TestCase):
    def setUp(self):
        send_magic_link_email("producer@example.com", "tok123")
        self.sent = mail.outbox[0]
        self.message = self.sent.message()

    def test_message_id_domain_matches_from_domain(self):
        """Django defaults Message-ID to socket.getfqdn() — the container or
        dev-machine hostname, which never matches the From domain. Spam filters
        score that mismatch, and for magic-link auth a junked mail is a locked-out
        user, so this stays pinned.
        """
        _, from_address = parseaddr(self.sent.from_email)
        from_domain = from_address.rpartition("@")[2]
        message_id = self.message["Message-ID"]
        self.assertTrue(message_id.endswith(f"@{from_domain}>"), message_id)

    def test_message_id_never_leaks_the_host_name(self):
        self.assertNotIn("ip6.arpa", self.message["Message-ID"])
        self.assertNotIn(".local", self.message["Message-ID"])

    def test_sends_both_a_text_and_an_html_part(self):
        types = {part.get_content_type() for part in self.message.walk()}
        self.assertIn("text/plain", types)
        self.assertIn("text/html", types)

    def test_both_parts_carry_the_sign_in_link(self):
        expected = "https://noagendatalentsearch.com/auth/verify/tok123/"
        self.assertIn(expected, self.sent.body)
        html_body, content_type = self.sent.alternatives[0]
        self.assertEqual(content_type, "text/html")
        self.assertIn(expected, html_body)

    def test_marked_auto_generated_so_responders_do_not_reply(self):
        self.assertEqual(self.message["Auto-Submitted"], "auto-generated")

    def test_no_template_syntax_reaches_the_rendered_message(self):
        html_body, _ = self.sent.alternatives[0]
        for fragment in ("{{", "}}", "{%", "%}", "{#"):
            self.assertNotIn(fragment, self.sent.body)
            self.assertNotIn(fragment, html_body)

    def test_html_part_references_no_remote_assets(self):
        """Remote content is a spam signal and images are blocked by default on
        many clients; this message has to render with no network fetch."""
        html_body, _ = self.sent.alternatives[0]
        self.assertNotIn("<img", html_body.lower())
        self.assertNotIn("http://", html_body)


class MessageIdDomainFallbackTests(TestCase):
    @override_settings(MAIL_FROM="postmaster")
    def test_falls_back_when_mail_from_has_no_domain(self):
        from accounts.emails import DEFAULT_MESSAGE_ID_DOMAIN, _message_id_domain

        self.assertEqual(_message_id_domain(), DEFAULT_MESSAGE_ID_DOMAIN)

    @override_settings(MAIL_FROM="No Agenda <hello@noagendatalentsearch.com>")
    def test_reads_the_domain_out_of_a_display_name_address(self):
        from accounts.emails import _message_id_domain

        self.assertEqual(_message_id_domain(), "noagendatalentsearch.com")
