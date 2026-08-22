from django.core.cache import cache
from django.test import TestCase

from core.models import Settings


class HealthzTests(TestCase):
    def test_healthz_returns_200_with_db_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class HomeTests(TestCase):
    def test_home_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class AboutTests(TestCase):
    def test_about_returns_200(self):
        response = self.client.get("/about/")
        self.assertEqual(response.status_code, 200)

    def test_about_renders_house_rules(self):
        response = self.client.get("/about/")
        self.assertContains(response, "House Rules")

    def test_about_renders_live_vote_eligibility_hours_not_hardcoded(self):
        cache.clear()
        Settings.objects.filter(key="vote_eligibility_hours").update(value_json=12)
        response = self.client.get("/about/")
        self.assertContains(response, "12 hours after signup")
        self.assertNotContains(response, "48 hours after signup")

    def test_about_says_accounts_can_rate_immediately_when_delay_is_off(self):
        cache.clear()
        Settings.objects.filter(key="vote_eligibility_hours").update(value_json=0)
        response = self.client.get("/about/")
        self.assertContains(response, "as soon as they sign in")
        self.assertNotContains(response, "0 hours after signup")
