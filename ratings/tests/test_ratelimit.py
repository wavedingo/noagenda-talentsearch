from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from candidates.tests.helpers import make_candidate
from ratings.models import Rating
from ratings.ratelimit import RATINGS_PER_MINUTE, rating_rate_limited
from ratings.tests.test_services import make_live_demo, make_voter


class RatingRateLimitTests(TestCase):
    def test_under_the_cap_is_allowed(self):
        user = make_voter()
        self.assertFalse(rating_rate_limited(user))

    def test_thirty_recent_updates_block_the_next(self):
        user = make_voter()
        now = timezone.now()
        for i in range(RATINGS_PER_MINUTE):
            other = make_candidate(email=f"c{i}@example.com", stage_name=f"C{i}")
            other_demo = make_live_demo(other)
            Rating.objects.create(
                user=user,
                rateable_type=Rating.RateableType.DEMO,
                rateable_id=other_demo.pk,
                stars=3,
            )
        self.assertTrue(rating_rate_limited(user))
        Rating.objects.filter(user=user).update(updated_at=now - timedelta(minutes=2))
        self.assertFalse(rating_rate_limited(user))
