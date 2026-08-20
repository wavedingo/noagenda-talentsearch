from django.conf import settings
from django.test import TestCase


class StaticFilesConfigTests(TestCase):
    def test_whitenoise_middleware_installed(self):
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", settings.MIDDLEWARE)

    def test_static_root_is_configured(self):
        self.assertTrue(str(settings.STATIC_ROOT).endswith("staticfiles"))

    def test_dev_uses_plain_static_storage_not_manifest(self):
        # DEBUG is True in the local/test env (no APP_ENV=production set), so
        # the manifest storage (which requires collectstatic to have run)
        # must not be selected here, or `{% static %}` lookups would break
        # without a manual collectstatic step in every dev/test environment.
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )


class EmailBackendConfigTests(TestCase):
    def test_no_resend_key_configured_in_this_environment(self):
        # Django's test runner unconditionally overrides settings.EMAIL_BACKEND
        # to the locmem backend for the whole suite (so mail.outbox works),
        # which makes the resulting EMAIL_BACKEND value untestable here. What
        # IS testable, and is the actual precondition config/settings.py
        # branches on, is that RESEND_API_KEY is unset in this environment --
        # confirming the console-backend branch is the one that would run.
        self.assertEqual(settings.RESEND_API_KEY, "")
