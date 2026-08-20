from django.test import TestCase

from accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_defaults_to_producer_role(self):
        user = User.objects.create_user(email="Producer@Example.com")
        self.assertEqual(user.role, User.Role.PRODUCER)
        self.assertEqual(user.email, "producer@example.com")  # normalized lowercase

    def test_create_user_has_no_usable_password(self):
        user = User.objects.create_user(email="producer2@example.com")
        self.assertFalse(user.has_usable_password())

    def test_moderator_is_staff_not_superuser(self):
        user = User.objects.create_user(email="mod@example.com", role=User.Role.MODERATOR)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_admin_is_staff_and_superuser(self):
        user = User.objects.create_superuser(email="admin@example.com")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_producer_is_neither_staff_nor_superuser(self):
        user = User.objects.create_user(email="plain@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_banned_user_is_not_active(self):
        from django.utils import timezone

        user = User.objects.create_user(email="banned@example.com")
        self.assertTrue(user.is_active)
        user.banned_at = timezone.now()
        user.save()
        self.assertFalse(user.is_active)

    def test_email_is_unique(self):
        from django.db import IntegrityError

        User.objects.create_user(email="dup@example.com")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="dup@example.com")
