from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def _create(self, email, display_name, role, signup_ip, **extra):
        if not email:
            raise ValueError("email is required")
        user = self.model(
            email=self.normalize_email(email).lower(),
            display_name=display_name,
            role=role,
            signup_ip=signup_ip,
            **extra,
        )
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, display_name="", role=None, signup_ip=None, **extra):
        return self._create(email, display_name, role or User.Role.PRODUCER, signup_ip, **extra)

    def create_superuser(self, email, display_name="", **extra):
        return self._create(email, display_name, User.Role.ADMIN, None, **extra)


class User(AbstractBaseUser):
    class Role(models.TextChoices):
        PRODUCER = "producer", "Producer"
        MODERATOR = "moderator", "Moderator"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PRODUCER)
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    vote_eligible_override_at = models.DateTimeField(null=True, blank=True)
    signup_ip = models.GenericIPAddressField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def is_staff(self):
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    @property
    def is_superuser(self):
        return self.role == self.Role.ADMIN

    @property
    def is_active(self):
        return self.banned_at is None and self.deleted_at is None

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_staff
