from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from episodes.models import Episode
from episodes.views import EPISODES_PER_PAGE


def make_episode(number, **overrides):
    fields = {
        "guid": f"{number}.noagendanotes.com",
        "raw_guid": f"http://{number}.noagendanotes.com",
        "episode_number": number,
        "title_raw": f'{number} - "Episode {number}"',
        "title_display": f"Episode {number}",
        "published_at": timezone.now() - timedelta(days=1900 - number),
        "link_url": f"http://{number}.noagendanotes.com",
        "artwork_url": f"https://noagendaassets.com/enc/na-{number}-art-feed.jpg",
        "enclosure_url": f"https://op3.dev/e/mp3s.nashownotes.com/NA-{number}.mp3",
        "duration_sec": 9292,
    }
    fields.update(overrides)
    return Episode.objects.create(**fields)


class EpisodeListTests(TestCase):
    def test_empty_state(self):
        response = self.client.get(reverse("episodes:list"))
        self.assertContains(response, "No episodes synced yet")

    def test_newest_first(self):
        for number in (1890, 1896, 1893):
            make_episode(number)
        response = self.client.get(reverse("episodes:list"))
        numbers = [e.episode_number for e in response.context["page_obj"]]
        self.assertEqual(numbers, [1896, 1893, 1890])

    def test_entire_episode_card_links_to_the_detail_page(self):
        make_episode(1896)
        response = self.client.get(reverse("episodes:list"))
        detail = reverse("episodes:detail", args=[1896])
        self.assertContains(response, f'class="episode-card-link" href="{detail}"')
        self.assertNotContains(response, f'<a href="{detail}">1896')

    def test_paginates_at_twenty(self):
        for number in range(1890, 1890 + EPISODES_PER_PAGE + 5):
            make_episode(number)

        first = self.client.get(reverse("episodes:list"))
        self.assertEqual(len(first.context["page_obj"]), EPISODES_PER_PAGE)
        second = self.client.get(reverse("episodes:list"), {"page": 2})
        self.assertEqual(len(second.context["page_obj"]), 5)

    def test_labels_the_floor_so_it_does_not_read_as_a_broken_archive(self):
        response = self.client.get(reverse("episodes:list"))
        self.assertContains(response, "Vote on your favorite guest-hosts")
        self.assertContains(response, "isn't a full archive of episodes")
        self.assertContains(response, "1890")

    def test_guest_host_badge_is_for_tagged_appearances_not_feed_names(self):
        from ratings.models import Appearance

        make_episode(1896, feed_guest_hosts=["Rob Dew"])
        tagged = make_episode(1895)
        Appearance.objects.create(
            episode=tagged,
            guest_name="A Candidate",
            rateable_until=timezone.now(),
        )
        response = self.client.get(reverse("episodes:list"))
        body = response.content.decode()
        self.assertIn("Guest host: A Candidate", body)
        # Feed-declared names are not the badge — tagging is (Phase 2 decision 2).
        self.assertEqual(body.count("badge"), 1)
        self.assertNotIn("Guest host: Rob Dew", body)

    def test_never_renders_the_op3_enclosure_url(self):
        # Every request through the OP3 prefix registers as a download in the
        # show's own statistics (spec 3.4).
        make_episode(1896)
        response = self.client.get(reverse("episodes:list"))
        self.assertNotContains(response, "op3.dev")


class EpisodeDetailTests(TestCase):
    def test_renders_episode(self):
        make_episode(1896, feed_guest_hosts=["Rob Dew"])
        response = self.client.get(reverse("episodes:detail", args=[1896]))
        self.assertContains(response, "Episode 1896")
        self.assertContains(response, "Rob Dew")
        self.assertContains(response, "http://1896.noagendanotes.com")

    def test_unknown_number_is_404(self):
        response = self.client.get(reverse("episodes:detail", args=[1234]))
        self.assertEqual(response.status_code, 404)

    def test_empty_guest_host_state(self):
        make_episode(1895)
        response = self.client.get(reverse("episodes:detail", args=[1895]))
        self.assertContains(response, "No guest host tagged on this one yet.")

    def test_never_renders_the_op3_enclosure_url(self):
        make_episode(1896)
        response = self.client.get(reverse("episodes:detail", args=[1896]))
        self.assertNotContains(response, "op3.dev")


class TemplateSyntaxLeakTests(TestCase):
    """A multi-line `{# ... #}` is not a comment in Django -- only the single-
    line form is -- so one written across lines renders as body text on the
    live page. Cheap to guard, invisible in code review."""

    def test_no_raw_template_syntax_reaches_the_page(self):
        make_episode(1896, feed_guest_hosts=["Rob Dew"])
        for url in (reverse("episodes:list"), reverse("episodes:detail", args=[1896])):
            body = self.client.get(url).content.decode()
            for token in ("{#", "#}", "{%", "%}"):
                self.assertNotIn(token, body, f"{token} leaked into {url}")
