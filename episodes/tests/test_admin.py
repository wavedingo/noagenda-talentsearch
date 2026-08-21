"""Episode manager in Django admin (spec 4, item 2)."""

from unittest.mock import patch

import requests
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from episodes.models import Episode

from .test_sync import SyncTestCase, feed_ok
from .test_views import make_episode

RESYNC_URL = "/django-admin/episodes/episode/resync/"


class ResyncActionTests(SyncTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin@example.com")
        self.client.force_login(self.admin)

    def test_changelist_offers_the_resync_button(self):
        make_episode(1896)
        response = self.client.get(reverse("admin:episodes_episode_changelist"))
        self.assertContains(response, "Re-sync feed now")

    def test_post_runs_a_sync(self):
        with feed_ok():
            response = self.client.post(RESYNC_URL, follow=True)

        self.assertEqual(Episode.objects.count(), 3)
        self.assertContains(response, "3 created")

    def test_get_is_rejected(self):
        # A sync is a write, and admin pages get prefetched.
        response = self.client.get(RESYNC_URL)
        self.assertEqual(response.status_code, 405)

    def test_failure_is_reported_not_swallowed(self):
        with patch("episodes.sync.requests.get", side_effect=requests.ConnectionError("boom")):
            response = self.client.post(RESYNC_URL, follow=True)
        self.assertContains(response, "Sync failed")

    def test_episodes_are_read_only_in_admin(self):
        # Every field is written by the sync job; a hand-edit would be silently
        # overwritten within 30 minutes.
        episode = make_episode(1896)
        response = self.client.get(
            reverse("admin:episodes_episode_change", args=[episode.pk])
        )
        self.assertNotContains(response, 'name="title_display"')


class ResyncPermissionTests(TestCase):
    def test_producer_cannot_trigger_a_sync(self):
        self.client.force_login(User.objects.create_user("producer@example.com"))
        response = self.client.post(RESYNC_URL)
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(Episode.objects.count(), 0)

    def test_anonymous_cannot_trigger_a_sync(self):
        response = self.client.post(RESYNC_URL)
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(Episode.objects.count(), 0)
