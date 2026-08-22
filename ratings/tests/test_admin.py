from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from candidates.models import Candidate
from candidates.tests.helpers import make_candidate, make_user
from episodes.tests.test_views import make_episode
from ratings.models import Appearance
from ratings.tests.test_services import RatingsTestCase


class AppearanceTaggingAdminTests(RatingsTestCase):
    def setUp(self):
        super().setUp()
        self.moderator = make_user("mod@example.com", role=User.Role.MODERATOR)
        self.client.force_login(self.moderator)
        self.episode = make_episode(1896, feed_guest_hosts=["Rob Dew"])
        self.url = reverse("admin:episodes_tag_appearances", args=[self.episode.pk])

    def test_a_moderator_can_open_the_tagging_page(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rob Dew")
        self.assertContains(response, "Tag as appearance")

    def test_tagging_from_the_feed_name(self):
        self.client.post(
            reverse("admin:episodes_appearance_tag", args=[self.episode.pk]),
            {"guest_name": "Rob Dew"},
        )
        appearance = Appearance.objects.get(episode=self.episode)
        self.assertEqual(appearance.guest_name, "Rob Dew")
        self.assertIsNone(appearance.candidate_id)

    def test_tagging_a_live_candidate(self):
        candidate = make_candidate(status=Candidate.Status.LIVE, stage_name="JR Varga")
        self.client.post(
            reverse("admin:episodes_appearance_tag", args=[self.episode.pk]),
            {"candidate": candidate.pk},
        )
        appearance = Appearance.objects.get(episode=self.episode)
        self.assertEqual(appearance.candidate, candidate)
        self.assertEqual(appearance.guest_name, "JR Varga")

    def test_linking_preserves_the_appearance_row(self):
        appearance = Appearance.objects.create(
            episode=self.episode,
            guest_name="Rob Dew",
            rateable_until=timezone.now() + timedelta(days=14),
        )
        candidate = make_candidate(status=Candidate.Status.LIVE, stage_name="Rob")
        self.client.post(
            reverse("admin:episodes_appearance_link", args=[self.episode.pk]),
            {"appearance_id": appearance.pk, "candidate_id": candidate.pk},
        )
        appearance.refresh_from_db()
        self.assertEqual(appearance.candidate, candidate)
        self.assertEqual(Appearance.objects.filter(episode=self.episode).count(), 1)

    def test_a_producer_cannot_tag(self):
        self.client.logout()
        producer = make_user("producer@example.com")
        self.client.force_login(producer)
        response = self.client.post(
            reverse("admin:episodes_appearance_tag", args=[self.episode.pk]),
            {"guest_name": "Rob Dew"},
        )
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(Appearance.objects.count(), 0)


class RankingsAdminTests(RatingsTestCase):
    def test_a_moderator_can_open_full_rankings(self):
        make_candidate(status=Candidate.Status.LIVE, stage_name="The Contender")
        self.client.force_login(make_user("mod@example.com", role=User.Role.MODERATOR))
        response = self.client.get(reverse("admin:candidates_rankings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Contender")
        self.assertContains(response, "Composite")
