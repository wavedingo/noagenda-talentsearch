from django.test import Client, TestCase, override_settings


class ErrorPageTests(TestCase):
    def test_404_uses_custom_template_not_framework_default(self):
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            client = Client(raise_request_exception=False)
            response = client.get("/this-page-does-not-exist/")
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, "can't find that page", status_code=404)

    def test_500_uses_custom_template_not_framework_default(self):
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            client = Client(raise_request_exception=False)
            response = client.get("/__test-500__/")
            self.assertEqual(response.status_code, 500)
            self.assertContains(response, "something went wrong", status_code=500)
