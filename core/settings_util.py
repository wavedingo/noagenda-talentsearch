from django.core.cache import cache

from .models import Settings

CACHE_PREFIX = "core:setting:"
CACHE_TTL_SECONDS = 60


def get_setting(key):
    cache_key = f"{CACHE_PREFIX}{key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["value"]

    try:
        row = Settings.objects.get(key=key)
    except Settings.DoesNotExist:
        raise KeyError(f"Unknown setting: {key}")

    cache.set(cache_key, {"value": row.value_json}, CACHE_TTL_SECONDS)
    return row.value_json
