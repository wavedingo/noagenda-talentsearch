from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import MagicLink, User
from accounts.tokens import consume_magic_link, create_magic_link, hash_token


class MagicLinkTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def test_create_magic_link_stores_hash_not_raw_token(self):
        raw_token = create_magic_link(self.user)
        link = MagicLink.objects.get(user=self.user)
        self.assertEqual(link.token_hash, hash_token(raw_token))
        self.assertNotEqual(link.token_hash, raw_token)

    def test_consume_valid_token_returns_user_and_marks_used(self):
        raw_token = create_magic_link(self.user)
        result = consume_magic_link(raw_token)
        self.assertEqual(result, self.user)
        link = MagicLink.objects.get(user=self.user)
        self.assertIsNotNone(link.used_at)

    def test_consume_same_token_twice_fails_second_time(self):
        raw_token = create_magic_link(self.user)
        consume_magic_link(raw_token)
        self.assertIsNone(consume_magic_link(raw_token))

    def test_consume_expired_token_fails(self):
        raw_token = create_magic_link(self.user)
        link = MagicLink.objects.get(user=self.user)
        link.expires_at = timezone.now() - timedelta(minutes=1)
        link.save()
        self.assertIsNone(consume_magic_link(raw_token))

    def test_consume_unknown_token_fails(self):
        self.assertIsNone(consume_magic_link("not-a-real-token"))
