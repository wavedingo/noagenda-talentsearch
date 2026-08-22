from django.conf import settings

from .turnstile import turnstile_enabled


def turnstile(request):
    return {
        "turnstile_enabled": turnstile_enabled(),
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
    }
