from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings

PROXY_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


def forwarded_request():
    """A request shaped the way one actually arrives in production: plain HTTP
    from Cloudflare/Render, with the real scheme only in X-Forwarded-Proto."""
    return RequestFactory().post(
        "/login/",
        HTTP_HOST="noagendatalentsearch.com",
        HTTP_ORIGIN="https://noagendatalentsearch.com",
        HTTP_X_FORWARDED_PROTO="https",
    )


@override_settings(
    ALLOWED_HOSTS=["noagendatalentsearch.com"], SECURE_PROXY_SSL_HEADER=PROXY_HEADER
)
class ForwardedProtoTests(TestCase):
    """Cloudflare and Render terminate TLS and forward plain HTTP to gunicorn.

    Without SECURE_PROXY_SSL_HEADER Django reads the request as http://, derives
    the expected CSRF origin from that, and rejects the https:// Origin the
    browser sent -- a 403 on every POST, the login form included, on a site whose
    health check is green. That was live in production once.
    """

    def test_request_is_recognised_as_secure(self):
        self.assertTrue(forwarded_request().is_secure())

    def test_expected_csrf_origin_matches_what_the_browser_sends(self):
        request = forwarded_request()
        self.assertEqual(request._current_scheme_host, request.META["HTTP_ORIGIN"])


@override_settings(ALLOWED_HOSTS=["noagendatalentsearch.com"])
class WithoutTheHeaderTests(TestCase):
    def test_csrf_origin_mismatches_when_the_header_is_not_trusted(self):
        """The failure this setting exists to prevent. If this ever stops
        mismatching, Django changed and the production setting can be revisited."""
        request = forwarded_request()
        self.assertEqual(request._current_scheme_host, "http://noagendatalentsearch.com")
        self.assertNotEqual(request._current_scheme_host, request.META["HTTP_ORIGIN"])


class ProxyHeaderIsProductionOnlyTests(TestCase):
    def test_header_is_not_trusted_in_this_environment(self):
        # config/settings.py sets SECURE_PROXY_SSL_HEADER only under
        # APP_ENV=production, which cannot be flipped after import. What is
        # testable here is the precondition it branches on: this environment is
        # development, so the header must be absent -- locally nothing strips it,
        # and a direct client could otherwise forge it to claim HTTPS.
        self.assertEqual(settings.APP_ENV, "development")
        self.assertIsNone(getattr(settings, "SECURE_PROXY_SSL_HEADER", None))
