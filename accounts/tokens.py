import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from .models import MagicLink

TOKEN_BYTES = 32
EXPIRY_MINUTES = 15


def generate_token():
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_magic_link(user, requested_ip=None):
    raw_token = generate_token()
    MagicLink.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        requested_ip=requested_ip,
        expires_at=timezone.now() + timedelta(minutes=EXPIRY_MINUTES),
    )
    return raw_token


def consume_magic_link(raw_token):
    token_hash = hash_token(raw_token)
    now = timezone.now()
    updated = MagicLink.objects.filter(
        token_hash=token_hash, used_at__isnull=True, expires_at__gte=now
    ).update(used_at=now)
    if not updated:
        return None
    return MagicLink.objects.get(token_hash=token_hash).user
