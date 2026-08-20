from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from candidates.models import Candidate
from episodes.models import Episode
from ratings.models import Appearance, Rating


class RatingsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="voter@example.com")
        candidate_user = User.objects.create_user(email="candidate@example.com")
        self.candidate = Candidate.objects.create(user=candidate_user, stage_name="The Contender")
        self.episode = Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw="x",
            title_display="x",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
        )

    def test_create_appearance(self):
        appearance = Appearance.objects.create(
            episode=self.episode,
            candidate=self.candidate,
            rateable_until=timezone.now(),
        )
        self.assertEqual(appearance.episode, self.episode)

    def test_duplicate_appearance_rejected(self):
        from django.db import IntegrityError

        Appearance.objects.create(episode=self.episode, candidate=self.candidate, rateable_until=timezone.now())
        with self.assertRaises(IntegrityError):
            Appearance.objects.create(episode=self.episode, candidate=self.candidate, rateable_until=timezone.now())

    def test_create_rating_for_demo(self):
        rating = Rating.objects.create(
            user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4
        )
        self.assertEqual(rating.stars, 4)

    def test_duplicate_rating_same_user_same_item_rejected(self):
        from django.db import IntegrityError

        Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4)
        with self.assertRaises(IntegrityError):
            Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=2)

    def test_same_user_can_rate_two_different_items(self):
        Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4)
        Rating.objects.create(user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=2, stars=5)
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 2)
