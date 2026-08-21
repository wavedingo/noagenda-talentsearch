"""The R2 switch (spec A.4, A.5).

The bucket doesn't exist yet, so nothing here talks to Cloudflare. What it does
check is that the settings block produces the right backend and options when the
credentials appear — the failure mode being a site that quietly keeps writing to
an ephemeral container filesystem in production.
"""

import importlib
from unittest import mock

from django.test import SimpleTestCase

R2_ENV = {
    "R2_ACCOUNT_ID": "acct123",
    "R2_ACCESS_KEY_ID": "key123",
    "R2_SECRET_ACCESS_KEY": "secret123",
    "R2_BUCKET": "nats-media",
    "R2_PUBLIC_BASE_URL": "https://media.noagendatalentsearch.com/",
    "SECRET_KEY": "test-secret",
    "DATABASE_URL": "sqlite:///test.sqlite3",
}


def _settings_with(env):
    with mock.patch.dict("os.environ", env, clear=False):
        return importlib.reload(importlib.import_module("config.settings"))


class R2ConfigurationTests(SimpleTestCase):
    @classmethod
    def tearDownClass(cls):
        # The module was reloaded in-process; put it back the way the rest of
        # the suite expects to find it.
        _settings_with({})
        super().tearDownClass()

    def test_credentials_switch_the_default_storage_to_r2(self):
        module = _settings_with(R2_ENV)

        self.assertTrue(module.USE_R2)
        default = module.STORAGES["default"]
        self.assertEqual(default["BACKEND"], "storages.backends.s3.S3Storage")
        self.assertEqual(default["OPTIONS"]["bucket_name"], "nats-media")
        self.assertEqual(
            default["OPTIONS"]["endpoint_url"], "https://acct123.r2.cloudflarestorage.com"
        )

    def test_reads_go_to_the_public_domain_without_a_signed_query_string(self):
        options = _settings_with(R2_ENV).STORAGES["default"]["OPTIONS"]
        # Scheme and trailing slash stripped: django-storages wants a bare host.
        self.assertEqual(options["custom_domain"], "media.noagendatalentsearch.com")
        self.assertFalse(options["querystring_auth"])
        # R2 has no ACL concept; sending one is an error, not a no-op.
        self.assertIsNone(options["default_acl"])

    def test_uploads_never_overwrite_each_other(self):
        options = _settings_with(R2_ENV).STORAGES["default"]["OPTIONS"]
        self.assertFalse(options["file_overwrite"])

    def test_partial_credentials_fall_back_to_local_disk(self):
        """Half-configured must mean off, not a backend that 500s on every upload."""
        partial = {**R2_ENV, "R2_SECRET_ACCESS_KEY": ""}
        module = _settings_with(partial)

        self.assertFalse(module.USE_R2)
        self.assertEqual(
            module.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )
