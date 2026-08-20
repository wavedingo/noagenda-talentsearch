from django.test import TestCase
from django.utils import timezone

from episodes.models import Episode


class EpisodeModelTests(TestCase):
    def test_create_episode(self):
        episode = Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw='1895 - "XY You\'re Out"',
            title_display="XY You're Out",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
            artwork_url="https://noagendaassets.com/enc/x_na-1895-art-feed.jpg",
            enclosure_url="https://op3.dev/e/mp3s.nashownotes.com/NA-1895.mp3",
            duration_sec=11050,
        )
        self.assertEqual(episode.episode_number, 1895)

    def test_guid_is_unique(self):
        from django.db import IntegrityError

        Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw="x",
            title_display="x",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
        )
        with self.assertRaises(IntegrityError):
            Episode.objects.create(
                guid="1895.noagendanotes.com",
                raw_guid="http://1895.noagendanotes.com/",
                episode_number=1895,
                title_raw="x",
                title_display="x",
                published_at=timezone.now(),
                link_url="http://1895.noagendanotes.com",
            )
