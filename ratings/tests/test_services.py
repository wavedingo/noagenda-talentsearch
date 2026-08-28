from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from candidates.models import Candidate, Demo
from candidates.tests.helpers import make_candidate, make_user, set_runtime_setting
from episodes.tests.test_views import make_episode
from ratings.eligibility import is_vote_eligible, vote_eligible_at
from ratings.models import Appearance, Rating
from ratings.scoring import PRIOR_SEED
from ratings.services import (
    RatingError,
    community_favorites,
    public_rating_summary,
    recompute_scores,
    rising_demos,
    show_appearances,
    submit_rating,
    tag_appearance,
)


def make_voter(email="voter@example.com", hours_ago=72):
    user = make_user(email=email)
    user.created_at = timezone.now() - timedelta(hours=hours_ago)
    user.save(update_fields=["created_at"])
    return user


def make_live_demo(candidate, **extra):
    fields = {
        "original_path": "private/demos/x/original.mp3",
        "stream_path": "public/demos/x/stream.mp3",
        "status": Demo.Status.LIVE,
        "processing_state": Demo.ProcessingState.READY,
        "duration_sec": 32,
    }
    fields.update(extra)
    return Demo.objects.create(candidate=candidate, **fields)


class RatingsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)


class EligibilityTests(RatingsTestCase):
    def test_new_account_is_not_eligible(self):
        user = make_voter(hours_ago=1)
        self.assertFalse(is_vote_eligible(user))

    def test_account_past_the_delay_is_eligible(self):
        user = make_voter(hours_ago=49)
        self.assertTrue(is_vote_eligible(user))

    def test_zero_disables_the_gate(self):
        set_runtime_setting("vote_eligibility_hours", 0)
        user = make_voter(hours_ago=0)
        self.assertTrue(is_vote_eligible(user))

    def test_override_grants_early_access(self):
        user = make_voter(hours_ago=1)
        user.vote_eligible_override_at = timezone.now() - timedelta(minutes=1)
        user.save(update_fields=["vote_eligible_override_at"])
        self.assertTrue(is_vote_eligible(user))

    def test_raising_the_delay_re_gates_without_touching_existing_votes(self):
        user = make_voter(hours_ago=24)
        set_runtime_setting("vote_eligibility_hours", 12)
        self.assertTrue(is_vote_eligible(user))
        set_runtime_setting("vote_eligibility_hours", 48)
        self.assertFalse(is_vote_eligible(user))
        self.assertGreater(vote_eligible_at(user), timezone.now())


class SubmitRatingTests(RatingsTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(status=Candidate.Status.LIVE)
        self.demo = make_live_demo(self.candidate)
        self.voter = make_voter()

    def test_first_rating_creates_a_row(self):
        rating, created = submit_rating(self.voter, Rating.RateableType.DEMO, self.demo.pk, 5)
        self.assertTrue(created)
        self.assertEqual(rating.stars, 5)
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.rating_count, 1)
        self.assertEqual(self.demo.rating_avg, 5)

    def test_second_rating_from_the_same_account_updates(self):
        submit_rating(self.voter, Rating.RateableType.DEMO, self.demo.pk, 5)
        rating, created = submit_rating(self.voter, Rating.RateableType.DEMO, self.demo.pk, 2)
        self.assertFalse(created)
        self.assertEqual(Rating.objects.filter(user=self.voter).count(), 1)
        self.assertEqual(rating.stars, 2)
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.rating_avg, 2)

    def test_ineligible_account_is_rejected(self):
        newbie = make_voter(email="new@example.com", hours_ago=1)
        with self.assertRaises(RatingError):
            submit_rating(newbie, Rating.RateableType.DEMO, self.demo.pk, 5)
        self.assertEqual(Rating.objects.count(), 0)

    def test_pending_demo_is_not_rateable(self):
        self.demo.status = Demo.Status.PENDING
        self.demo.save(update_fields=["status"])
        with self.assertRaises(RatingError):
            submit_rating(self.voter, Rating.RateableType.DEMO, self.demo.pk, 5)

    def test_closed_appearance_is_not_rateable(self):
        episode = make_episode(1896)
        appearance = Appearance.objects.create(
            episode=episode,
            guest_name="Rob Dew",
            rateable_until=timezone.now() - timedelta(days=1),
        )
        with self.assertRaises(RatingError):
            submit_rating(self.voter, Rating.RateableType.APPEARANCE, appearance.pk, 4)


class ScoringJobTests(RatingsTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(status=Candidate.Status.LIVE)
        self.demo = make_live_demo(self.candidate)

    def test_no_ratings_seeds_the_prior(self):
        recompute_scores()
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.demo_score, PRIOR_SEED)
        self.assertIsNone(self.candidate.composite_score)

    def test_banned_ratings_are_excluded(self):
        voter = make_voter()
        banned = make_voter(email="banned@example.com")
        submit_rating(voter, Rating.RateableType.DEMO, self.demo.pk, 5)
        submit_rating(banned, Rating.RateableType.DEMO, self.demo.pk, 1)
        banned.banned_at = timezone.now()
        banned.save(update_fields=["banned_at"])
        recompute_scores()
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.rating_count, 1)
        self.assertEqual(self.demo.rating_avg, 5)

    def test_deleted_account_ratings_still_count(self):
        voter = make_voter()
        submit_rating(voter, Rating.RateableType.DEMO, self.demo.pk, 4)
        voter.deleted_at = timezone.now()
        voter.email = "deleted-1@deleted.noagendatalentsearch.com"
        voter.save(update_fields=["deleted_at", "email"])
        recompute_scores()
        self.demo.refresh_from_db()
        self.assertEqual(self.demo.rating_count, 1)
        self.assertEqual(self.demo.rating_avg, 4)

    def test_archived_demo_ratings_do_not_feed_the_composite(self):
        old = make_live_demo(self.candidate, original_path="private/demos/old/original.mp3")
        voter = make_voter()
        submit_rating(voter, Rating.RateableType.DEMO, old.pk, 1)
        old.status = Demo.Status.ARCHIVED
        old.save(update_fields=["status"])
        # The replacement live demo has no ratings; candidate demo_score is the prior,
        # not the archived 1-star.
        recompute_scores()
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.demo_score, PRIOR_SEED)

    def test_appearance_moves_a_candidate_onto_the_main_board(self):
        set_runtime_setting("min_votes_to_display", 1)
        episode = make_episode(1896)
        admin = make_user("mod@example.com")
        appearance = tag_appearance(episode, admin, candidate=self.candidate)
        recompute_scores()
        submit_rating(make_voter(), Rating.RateableType.APPEARANCE, appearance.pk, 5)
        self.candidate.refresh_from_db()
        self.assertIsNotNone(self.candidate.composite_score)
        entries = show_appearances()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].candidate, self.candidate)
        self.assertEqual(rising_demos(), [])

    def test_unlinked_appearance_without_ratings_stays_off_the_board(self):
        episode = make_episode(1896)
        admin = make_user("mod@example.com")
        tag_appearance(episode, admin, guest_name="Rob Dew")
        recompute_scores()
        self.candidate.refresh_from_db()
        self.assertIsNone(self.candidate.composite_score)
        self.assertEqual(show_appearances(), [])
        self.assertEqual(rising_demos(), [self.candidate])

    def test_unlinked_guest_with_enough_votes_shows_an_aggregate_summary(self):
        set_runtime_setting("min_votes_to_display", 1)
        episode_a = make_episode(1896)
        episode_b = make_episode(1895)
        admin = make_user("mod@example.com")
        tag_appearance(episode_a, admin, guest_name="Rob Dew")
        tag_appearance(episode_b, admin, guest_name="Rob Dew")
        recompute_scores()
        appearance_ids = list(Appearance.objects.values_list("pk", flat=True))
        voter_a = make_voter(email="a@example.com")
        voter_b = make_voter(email="b@example.com")
        for appearance_id in appearance_ids:
            submit_rating(voter_a, Rating.RateableType.APPEARANCE, appearance_id, 5)
            submit_rating(voter_b, Rating.RateableType.APPEARANCE, appearance_id, 4)
        entries = show_appearances()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].appearance_summary["count"], 4)
        self.assertAlmostEqual(entries[0].appearance_summary["average"], 4.5)

    def test_rated_guest_ranks_above_an_unrated_tagged_guest(self):
        set_runtime_setting("min_votes_to_display", 1)
        admin = make_user("mod@example.com")
        rob = tag_appearance(make_episode(1896), admin, guest_name="Rob Dew")
        tag_appearance(make_episode(1895), admin, guest_name="Matt Long")
        recompute_scores()
        submit_rating(make_voter(email="v1@example.com"), Rating.RateableType.APPEARANCE, rob.pk, 5)
        submit_rating(make_voter(email="v2@example.com"), Rating.RateableType.APPEARANCE, rob.pk, 5)
        entries = show_appearances()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].display_name, "Rob Dew")

    def test_withdrawn_candidates_are_dropped_from_scores(self):
        voter = make_voter()
        submit_rating(voter, Rating.RateableType.DEMO, self.demo.pk, 5)
        self.candidate.status = Candidate.Status.WITHDRAWN
        self.candidate.save(update_fields=["status"])
        recompute_scores()
        self.candidate.refresh_from_db()
        self.assertIsNone(self.candidate.composite_score)
        self.assertIsNone(self.candidate.demo_score)

    def test_below_threshold_summary_is_none(self):
        self.demo.rating_count = 3
        self.demo.rating_avg = 5
        self.assertIsNone(public_rating_summary(self.demo, threshold=10))

    def test_at_threshold_summary_returns_the_average(self):
        self.demo.rating_count = 10
        self.demo.rating_avg = 4.2
        summary = public_rating_summary(self.demo, threshold=10)
        self.assertEqual(summary["average"], 4.2)
        self.assertEqual(summary["count"], 10)
