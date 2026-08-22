from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.tokens import create_magic_link
from candidates.models import Candidate
from candidates.tests.helpers import make_candidate
from episodes.tests.test_views import make_episode
from ratings.models import Appearance, Rating
from ratings.tests.test_services import RatingsTestCase, make_live_demo, make_voter


class LeaderboardViewTests(RatingsTestCase):
    def test_empty_state_explains_the_main_board(self):
        response = self.client.get(reverse("ratings:leaderboard"))
        self.assertContains(response, "Community favorites")
        self.assertContains(response, "don't make it")
        self.assertContains(response, "Rising demos")

    def test_rising_lists_a_live_candidate_without_appearances(self):
        make_candidate(status=Candidate.Status.LIVE, stage_name="New Voice")
        response = self.client.get(reverse("ratings:leaderboard"))
        self.assertContains(response, "New Voice")
        self.assertContains(response, "The main board fills in")

    def test_no_raw_template_syntax_reaches_the_page(self):
        body = self.client.get(reverse("ratings:leaderboard")).content.decode()
        for token in ("{#", "#}", "{%", "%}"):
            self.assertNotIn(token, body)


class RatingViewTests(RatingsTestCase):
    def setUp(self):
        super().setUp()
        self.candidate = make_candidate(status=Candidate.Status.LIVE, stage_name="The Contender")
        self.demo = make_live_demo(self.candidate)
        self.voter = make_voter()
        self.client.get(reverse("accounts:verify", args=[create_magic_link(self.voter)]))

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        response = self.client.post(
            reverse("ratings:rate"),
            {
                "rateable_type": Rating.RateableType.DEMO,
                "rateable_id": self.demo.pk,
                "stars": 5,
                "next": reverse("candidates:detail", args=[self.candidate.slug]),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_eligible_producer_can_rate_a_live_demo(self):
        response = self.client.post(
            reverse("ratings:rate"),
            {
                "rateable_type": Rating.RateableType.DEMO,
                "rateable_id": self.demo.pk,
                "stars": 4,
                "next": reverse("candidates:detail", args=[self.candidate.slug]),
            },
        )
        self.assertRedirects(response, reverse("candidates:detail", args=[self.candidate.slug]))
        self.assertEqual(Rating.objects.filter(user=self.voter).count(), 1)
        page = self.client.get(reverse("candidates:detail", args=[self.candidate.slug]))
        self.assertContains(page, "Your rating: 4 stars")

    def test_rating_twice_does_not_duplicate(self):
        payload = {
            "rateable_type": Rating.RateableType.DEMO,
            "rateable_id": self.demo.pk,
            "stars": 5,
            "next": reverse("candidates:detail", args=[self.candidate.slug]),
        }
        self.client.post(reverse("ratings:rate"), payload)
        payload["stars"] = 2
        self.client.post(reverse("ratings:rate"), payload)
        self.assertEqual(Rating.objects.filter(user=self.voter).count(), 1)
        self.assertEqual(Rating.objects.get(user=self.voter).stars, 2)

    def test_get_is_rejected(self):
        self.assertEqual(self.client.get(reverse("ratings:rate")).status_code, 405)

    def test_open_redirect_is_ignored(self):
        response = self.client.post(
            reverse("ratings:rate"),
            {
                "rateable_type": Rating.RateableType.DEMO,
                "rateable_id": self.demo.pk,
                "stars": 5,
                "next": "https://evil.example/phish",
            },
        )
        self.assertRedirects(response, reverse("core:home"))

    def test_below_threshold_never_renders_zero_point_zero(self):
        page = self.client.get(reverse("candidates:detail", args=[self.candidate.slug]))
        self.assertContains(page, "Not enough ratings yet")
        self.assertNotContains(page, "0.0")


class AppearanceRatingViewTests(RatingsTestCase):
    def setUp(self):
        super().setUp()
        self.episode = make_episode(1896)
        self.appearance = Appearance.objects.create(
            episode=self.episode,
            guest_name="Rob Dew",
            rateable_until=timezone.now() + timedelta(days=14),
        )
        self.voter = make_voter()
        self.client.get(reverse("accounts:verify", args=[create_magic_link(self.voter)]))

    def test_episode_page_offers_a_widget(self):
        response = self.client.get(reverse("episodes:detail", args=[1896]))
        self.assertContains(response, "Rob Dew")
        self.assertContains(response, "Rate this")

    def test_closed_window_copy(self):
        self.appearance.rateable_until = timezone.now() - timedelta(days=1)
        self.appearance.save(update_fields=["rateable_until"])
        response = self.client.get(reverse("episodes:detail", args=[1896]))
        self.assertContains(response, "Ratings for this appearance are closed.")
        self.assertNotContains(response, "Rate this")


class CandidateListTopSortTests(RatingsTestCase):
    def test_top_sort_orders_by_demo_score(self):
        low = make_candidate(email="low@example.com", stage_name="Low Score", status=Candidate.Status.LIVE)
        high = make_candidate(email="high@example.com", stage_name="High Score", status=Candidate.Status.LIVE)
        low.demo_score = 3.1
        low.save(update_fields=["demo_score"])
        high.demo_score = 4.8
        high.save(update_fields=["demo_score"])
        body = self.client.get(reverse("candidates:list"), {"sort": "top"}).content.decode()
        self.assertLess(body.index("High Score"), body.index("Low Score"))
        self.assertEqual(self.client.get(reverse("candidates:list"), {"sort": "top"}).context["sort"], "top")
