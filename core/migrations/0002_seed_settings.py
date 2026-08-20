import os

from django.db import migrations


def _env_int(name, default):
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_float(name, default):
    raw = os.environ.get(name)
    return float(raw) if raw else default


def seed_settings(apps, schema_editor):
    Settings = apps.get_model("core", "Settings")
    defaults = {
        "vote_eligibility_hours": _env_int("VOTE_ELIGIBILITY_HOURS", 48),
        "min_votes_to_display": _env_int("MIN_VOTES_TO_DISPLAY", 10),
        "appearance_rating_window_days": _env_int("APPEARANCE_RATING_WINDOW_DAYS", 14),
        "demo_max_duration_sec": _env_int("DEMO_MAX_DURATION_SEC", 900),
        "demo_max_file_mb": _env_int("DEMO_MAX_FILE_MB", 50),
        "leaderboard_size": _env_int("LEADERBOARD_SIZE", 10),
        "score_weight_appearance": _env_float("SCORE_WEIGHT_APPEARANCE", 0.7),
        "score_weight_demo": _env_float("SCORE_WEIGHT_DEMO", 0.3),
        "auditions_open": True,
        "min_episode_number": _env_int("MIN_EPISODE_NUMBER", 1890),
    }
    for key, value in defaults.items():
        Settings.objects.get_or_create(key=key, defaults={"value_json": value})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed_settings, noop_reverse)]
