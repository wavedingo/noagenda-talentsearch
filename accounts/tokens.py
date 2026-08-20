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
    try:
        link = MagicLink.objects.get(token_hash=token_hash)
    except MagicLink.DoesNotExist:
        return None
    if link.used_at is not None:
        return None
    if link.expires_at < timezone.now():
        return None
    link.used_at = timezone.now()
    link.save(update_fields=["used_at"])
    return link.user
