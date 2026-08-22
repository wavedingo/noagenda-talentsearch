"""Cloudflare Turnstile (spec A.1 / §8). Credential-gated like Resend and R2."""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_enabled():
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def verify_turnstile(token, ip=None):
    if not turnstile_enabled():
        return True
    if not token:
        return False
    try:
        response = requests.post(
            VERIFY_URL,
            data={
                "secret": settings.TURNSTILE_SECRET_KEY,
                "response": token,
                "remoteip": ip or "",
            },
            timeout=5,
        )
        response.raise_for_status()
        return bool(response.json().get("success"))
    except Exception:
        logger.exception("turnstile verify failed")
        return False
