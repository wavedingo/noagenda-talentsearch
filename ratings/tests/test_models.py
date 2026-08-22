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
        self.candidate = Candidate.objects.create(
            user=candidate_user, slug="the-contender", stage_name="The Contender"
        )
        self.episode = Episode.objects.create(
            guid="1895.noagendanotes.com",
            raw_guid="http://1895.noagendanotes.com",
            episode_number=1895,
            title_raw="x",
            title_display="x",
            published_at=timezone.now(),
            link_url="http://1895.noagendanotes.com",
        )

    def test_create_appearance_with_candidate(self):
        appearance = Appearance.objects.create(
            episode=self.episode,
            candidate=self.candidate,
            guest_name="The Contender",
            rateable_until=timezone.now(),
        )
        self.assertEqual(appearance.display_name, "The Contender")

    def test_unlinked_appearance_uses_guest_name(self):
        appearance = Appearance.objects.create(
            episode=self.episode,
            guest_name="Rob Dew",
            rateable_until=timezone.now(),
        )
        self.assertIsNone(appearance.candidate_id)
        self.assertEqual(appearance.display_name, "Rob Dew")

    def test_duplicate_linked_appearance_rejected(self):
        from django.db import IntegrityError

        Appearance.objects.create(
            episode=self.episode,
            candidate=self.candidate,
            guest_name="The Contender",
            rateable_until=timezone.now(),
        )
        with self.assertRaises(IntegrityError):
            Appearance.objects.create(
                episode=self.episode,
                candidate=self.candidate,
                guest_name="The Contender 2",
                rateable_until=timezone.now(),
            )

    def test_duplicate_guest_name_on_same_episode_rejected(self):
        from django.db import IntegrityError

        Appearance.objects.create(
            episode=self.episode, guest_name="Rob Dew", rateable_until=timezone.now()
        )
        with self.assertRaises(IntegrityError):
            Appearance.objects.create(
                episode=self.episode, guest_name="Rob Dew", rateable_until=timezone.now()
            )

    def test_two_unlinked_names_on_same_episode_are_allowed(self):
        Appearance.objects.create(
            episode=self.episode, guest_name="Rob Dew", rateable_until=timezone.now()
        )
        Appearance.objects.create(
            episode=self.episode, guest_name="Someone Else", rateable_until=timezone.now()
        )
        self.assertEqual(self.episode.appearances.count(), 2)

    def test_create_rating_for_demo(self):
        rating = Rating.objects.create(
            user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4
        )
        self.assertEqual(rating.stars, 4)

    def test_duplicate_rating_same_user_same_item_rejected(self):
        from django.db import IntegrityError

        Rating.objects.create(
            user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4
        )
        with self.assertRaises(IntegrityError):
            Rating.objects.create(
                user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=2
            )

    def test_same_user_can_rate_two_different_items(self):
        Rating.objects.create(
            user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=1, stars=4
        )
        Rating.objects.create(
            user=self.user, rateable_type=Rating.RateableType.DEMO, rateable_id=2, stars=5
        )
        self.assertEqual(Rating.objects.filter(user=self.user).count(), 2)
