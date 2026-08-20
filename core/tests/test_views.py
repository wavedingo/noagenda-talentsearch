from django.test import TestCase


class HealthzTests(TestCase):
    def test_healthz_returns_200_with_db_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class HomeTests(TestCase):
    def test_home_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
