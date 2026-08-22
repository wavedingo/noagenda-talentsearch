from django.contrib.admin.sites import site
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.models import Settings
from core.settings_util import get_setting
from moderation.models import AdminAuditLog


class SettingsAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@example.com")
        self.moderator = User.objects.create_user(
            email="mod@example.com", role=User.Role.MODERATOR
        )
        self.client.force_login(self.admin)

    def test_settings_are_registered_in_admin(self):
        self.assertIn(Settings, site._registry)

    def test_changing_the_vote_delay_asks_for_confirmation(self):
        from core.settings_util import set_setting

        set_setting("vote_eligibility_hours", 48)
        url = reverse("admin:core_settings_change", args=["vote_eligibility_hours"])
        response = self.client.post(url, {"value_json": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm vote delay change")
        self.assertEqual(get_setting("vote_eligibility_hours"), 48)

    def test_admin_can_set_vote_eligibility_to_zero(self):
        url = reverse("admin:core_settings_change", args=["vote_eligibility_hours"])
        response = self.client.post(url, {"value_json": "0", "confirm": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Settings.objects.get(key="vote_eligibility_hours").value_json, 0)
        self.assertEqual(get_setting("vote_eligibility_hours"), 0)
        self.assertTrue(
            AdminAuditLog.objects.filter(
                action="settings.change", metadata_json__key="vote_eligibility_hours"
            ).exists()
        )

    def test_a_moderator_can_change_the_vote_delay(self):
        self.client.force_login(self.moderator)
        url = reverse("admin:core_settings_change", args=["vote_eligibility_hours"])
        response = self.client.post(url, {"value_json": "0", "confirm": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_setting("vote_eligibility_hours"), 0)

    def test_a_moderator_cannot_change_score_weights(self):
        self.client.force_login(self.moderator)
        original = Settings.objects.get(key="score_weight_appearance").value_json
        url = reverse("admin:core_settings_change", args=["score_weight_appearance"])
        self.client.post(url, {"value_json": "1"})
        self.assertEqual(Settings.objects.get(key="score_weight_appearance").value_json, original)

    def test_moderator_can_change_the_appearance_rating_window(self):
        self.client.force_login(self.moderator)
        url = reverse("admin:core_settings_change", args=["appearance_rating_window_days"])
        response = self.client.post(url, {"value_json": "21"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_setting("appearance_rating_window_days"), 21)

    def test_settings_changelist_lists_the_vote_delay_and_appearance_window(self):
        response = self.client.get(reverse("admin:core_settings_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vote_eligibility_hours")
        self.assertContains(response, "appearance_rating_window_days")

    def test_settings_cannot_be_deleted(self):
        url = reverse("admin:core_settings_delete", args=["vote_eligibility_hours"])
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Settings.objects.filter(key="vote_eligibility_hours").exists())
