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

    def test_logout_button_is_on_the_account_page(self):
        response = self.client.get(reverse("accounts:account"))
        self.assertContains(response, 'action="/logout/"')
        self.assertContains(response, "Log out")

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
        account_response = self.client.get(reverse("accounts:account"))
        self.assertEqual(account_response.status_code, 302)


class AccountFeedbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com", display_name="Old Name")
        raw_token = create_magic_link(self.user)
        self.client.get(reverse("accounts:verify", args=[raw_token]))

    def test_saving_confirms_and_redirects(self):
        """Without a message the page re-rendered identically and the save
        looked like it had done nothing. Redirecting also stops a refresh from
        re-posting the form."""
        response = self.client.post(
            reverse("accounts:account"), {"display_name": "New Name"}, follow=True
        )
        self.assertRedirects(response, reverse("accounts:account"))
        self.assertContains(response, "Saved.")

    def test_page_does_not_claim_to_change_the_public_stage_name(self):
        """display_name is account metadata that appears on no public page.
        The audition name is Candidate.stage_name and only changes through
        pre-moderation, so this page has to send people there instead of
        letting them edit the wrong field and think the site is broken."""
        response = self.client.get(reverse("accounts:account"))
        self.assertContains(response, "Only site moderators see this")
        self.assertContains(response, "Stage Name")
        self.assertContains(response, reverse("candidates:audition"))

    def test_delete_is_visually_separated_and_marked_dangerous(self):
        response = self.client.get(reverse("accounts:account"))
        self.assertContains(response, "danger-zone")
        self.assertContains(response, "button-danger")
        self.assertContains(response, "It cannot be undone.")
