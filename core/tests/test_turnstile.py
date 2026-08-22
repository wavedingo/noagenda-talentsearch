from unittest.mock import patch

from django.test import TestCase, override_settings

from core.turnstile import turnstile_enabled, verify_turnstile


class TurnstileDisabledTests(TestCase):
    def test_missing_keys_mean_the_check_is_off(self):
        self.assertFalse(turnstile_enabled())
        self.assertTrue(verify_turnstile(""))


@override_settings(TURNSTILE_SITE_KEY="site", TURNSTILE_SECRET_KEY="secret")
class TurnstileEnabledTests(TestCase):
    def test_blank_token_fails(self):
        self.assertTrue(turnstile_enabled())
        self.assertFalse(verify_turnstile(""))

    @patch("core.turnstile.requests.post")
    def test_cloudflare_success_passes(self, post):
        post.return_value.json.return_value = {"success": True}
        post.return_value.raise_for_status.return_value = None
        self.assertTrue(verify_turnstile("token", "1.2.3.4"))

    @patch("core.turnstile.requests.post")
    def test_cloudflare_failure_is_closed(self, post):
        post.return_value.json.return_value = {"success": False}
        post.return_value.raise_for_status.return_value = None
        self.assertFalse(verify_turnstile("token"))
