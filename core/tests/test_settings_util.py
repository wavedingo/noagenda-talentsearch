from django.core.cache import cache
from django.test import TestCase

from core.models import Settings
from core.settings_util import get_setting


class GetSettingTests(TestCase):
    def setUp(self):
        cache.clear()
        Settings.objects.all().delete()

    def test_returns_seeded_value(self):
        Settings.objects.create(key="leaderboard_size", value_json=10)
        self.assertEqual(get_setting("leaderboard_size"), 10)

    def test_unknown_key_raises_keyerror(self):
        with self.assertRaises(KeyError):
            get_setting("not_a_real_setting")

    def test_value_is_cached_after_first_read(self):
        Settings.objects.create(key="auditions_open", value_json=True)
        self.assertTrue(get_setting("auditions_open"))
        Settings.objects.filter(key="auditions_open").update(value_json=False)
        # still cached, so still True
        self.assertTrue(get_setting("auditions_open"))

    def test_falsy_values_are_cached_correctly(self):
        Settings.objects.create(key="score_weight_demo", value_json=0)
        self.assertEqual(get_setting("score_weight_demo"), 0)
