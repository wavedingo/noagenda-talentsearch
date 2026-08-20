from django.test import TestCase

from accounts.models import User
from accounts.ratelimit import (
    email_link_requests_exceeded,
    ip_link_requests_exceeded,
    ip_signup_limit_exceeded,
)
from accounts.tokens import create_magic_link


class RateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="producer@example.com")

    def test_email_limit_not_exceeded_below_threshold(self):
        for _ in range(2):
            create_magic_link(self.user)
        self.assertFalse(email_link_requests_exceeded("producer@example.com"))

    def test_email_limit_exceeded_at_threshold(self):
        for _ in range(3):
            create_magic_link(self.user)
        self.assertTrue(email_link_requests_exceeded("producer@example.com"))

    def test_ip_limit_not_exceeded_below_threshold(self):
        for _ in range(9):
            create_magic_link(self.user, requested_ip="1.2.3.4")
        self.assertFalse(ip_link_requests_exceeded("1.2.3.4"))

    def test_ip_limit_exceeded_at_threshold(self):
        for _ in range(10):
            create_magic_link(self.user, requested_ip="1.2.3.4")
        self.assertTrue(ip_link_requests_exceeded("1.2.3.4"))

    def test_signup_ip_limit_exceeded_at_threshold(self):
        for i in range(5):
            User.objects.create_user(email=f"new{i}@example.com", signup_ip="5.6.7.8")
        self.assertTrue(ip_signup_limit_exceeded("5.6.7.8"))

    def test_signup_ip_limit_ignores_none(self):
        self.assertFalse(ip_signup_limit_exceeded(None))
