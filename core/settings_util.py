from django.core.cache import cache

from .models import Settings

CACHE_PREFIX = "core:setting:"
CACHE_TTL_SECONDS = 60


def _cache_key(key):
    return f"{CACHE_PREFIX}{key}"


def get_setting(key):
    cache_key = _cache_key(key)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["value"]

    try:
        row = Settings.objects.get(key=key)
    except Settings.DoesNotExist:
        raise KeyError(f"Unknown setting: {key}")

    cache.set(cache_key, {"value": row.value_json}, CACHE_TTL_SECONDS)
    return row.value_json


def set_setting(key, value):
    """Write a runtime setting and drop this process's cache for that key.

    Other gunicorn workers keep their own 60s locmem copy, so a change is
    fully live within a minute (or immediately after a restart).
    """
    Settings.objects.update_or_create(key=key, defaults={"value_json": value})
    cache.delete(_cache_key(key))
    return value
