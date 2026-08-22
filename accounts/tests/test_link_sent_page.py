from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(MAIL_FROM="No Agenda Talent Search <hello@noagendatalentsearch.com>")
class LinkSentPageTests(TestCase):
    """Yahoo and Outlook both junk the sign-in mail with SPF, DKIM and DMARC all
    passing -- it is new-domain reputation, not configuration. Until that clears,
    this page is the only thing standing between a producer and concluding the
    site is broken, so the spam-folder guidance is load-bearing.
    """

    def setUp(self):
        self.response = self.client.post(
            reverse("accounts:request_link"), {"email": "producer@example.com"}
        )

    def test_tells_people_to_check_their_spam_folder(self):
        self.assertContains(self.response, "spam or junk folder")

    def test_shows_the_sender_address_to_allowlist(self):
        self.assertContains(self.response, "hello@noagendatalentsearch.com")

    def test_does_not_leak_the_display_name_into_the_allowlist_hint(self):
        # parseaddr must strip "No Agenda Talent Search <...>" down to the bare
        # address; the full MAIL_FROM string is not something you can add to
        # a contacts list.
        self.assertNotContains(self.response, "&lt;hello@")

    def test_offers_a_way_to_request_another_link(self):
        self.assertContains(self.response, reverse("accounts:request_link"))

    def test_no_template_syntax_reaches_the_page(self):
        body = self.response.content.decode()
        for fragment in ("{{", "}}", "{%", "%}", "{#"):
            self.assertNotIn(fragment, body)
