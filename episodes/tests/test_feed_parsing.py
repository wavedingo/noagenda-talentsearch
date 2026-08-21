"""Parser tests (spec 3.4).

`feed_sample.xml` is trimmed from a real fetch of the live feed on 2026-08-20,
so these run against the feed's actual quirks rather than an idealized one:
episodes 1896 (guest host), 1895, 1890 (carries a `<description>` blob), 1889
(below the floor), 1887 (trailing whitespace in the title), the channel-level
`<podcast:liveItem>`, and one synthetic item whose title has no number.
"""

from pathlib import Path

from django.test import TestCase

from episodes.feed import (
    ItemParseError,
    clean_title,
    normalize_guid,
    parse_duration,
    parse_episode_number,
    parse_feed,
)

FIXTURE = Path(__file__).parent / "fixtures" / "feed_sample.xml"


def load_fixture():
    return FIXTURE.read_bytes()


class NormalizeGuidTests(TestCase):
    def test_strips_scheme_case_and_trailing_slash(self):
        # All four spellings of the same episode. If any of these produced a
        # distinct key, a scheme change at the publisher would silently
        # duplicate the entire back catalogue.
        variants = [
            "http://1895.noagendanotes.com",
            "https://1895.noagendanotes.com",
            "HTTP://1895.NoAgendaNotes.com/",
            "  https://1895.noagendanotes.com/  ",
        ]
        self.assertEqual({normalize_guid(v) for v in variants}, {"1895.noagendanotes.com"})

    def test_non_url_guid_survives(self):
        self.assertEqual(normalize_guid("NA-1896 Live"), "na-1896 live")


class EpisodeNumberTests(TestCase):
    def test_parses_leading_digits(self):
        self.assertEqual(parse_episode_number('1895 - "XY You\'re Out"'), 1895)

    def test_tolerates_leading_whitespace(self):
        self.assertEqual(parse_episode_number(' 1861 - "Cone of Uncertainty" '), 1861)

    def test_no_number_is_a_parse_error(self):
        with self.assertRaises(ItemParseError):
            parse_episode_number("Bonus - No Number In This Title")


class CleanTitleTests(TestCase):
    def test_strips_number_prefix_and_quotes(self):
        self.assertEqual(clean_title('1895 - "XY You\'re Out"'), "XY You're Out")

    def test_keeps_interior_apostrophe(self):
        self.assertEqual(clean_title('1889 - "Producer\'s Tribute to JCD"'), "Producer's Tribute to JCD")

    def test_strips_whitespace_inside_the_cdata(self):
        self.assertEqual(clean_title('1887 - "The Stick Works" '), "The Stick Works")

    def test_strips_curly_quotes(self):
        self.assertEqual(clean_title("1890 - “Flock Off!”"), "Flock Off!")

    def test_leaves_an_unquoted_title_alone(self):
        self.assertEqual(clean_title("1890 - Flock Off!"), "Flock Off!")


class DurationTests(TestCase):
    def test_integer_seconds(self):
        self.assertEqual(parse_duration("9292"), 9292)

    def test_clock_format_is_accepted(self):
        self.assertEqual(parse_duration("02:34:52"), 9292)
        self.assertEqual(parse_duration("15:00"), 900)

    def test_missing_duration_is_none(self):
        self.assertIsNone(parse_duration(""))

    def test_garbage_raises(self):
        with self.assertRaises(ItemParseError):
            parse_duration("about an hour")


class ParseFeedTests(TestCase):
    def setUp(self):
        self.episodes, self.failures = parse_feed(load_fixture())
        self.by_number = {e["episode_number"]: e for e in self.episodes}

    def test_live_item_does_not_become_an_episode(self):
        # <podcast:liveItem> is a child of <channel>, a sibling of the items --
        # so iterating channel/item skips it structurally. Asserted rather than
        # assumed, since a publisher could move it.
        self.assertNotIn("na-1896 live", {e["guid"] for e in self.episodes})
        titles = {e["title_raw"] for e in self.episodes}
        self.assertNotIn("No Agenda Episode 1896 - Live", titles)

    def test_unparseable_item_is_reported_not_fatal(self):
        self.assertEqual(len(self.failures), 1)
        self.assertIn("Bonus", self.failures[0][0])
        # The rest of the feed still parsed.
        self.assertEqual(sorted(self.by_number), [1887, 1889, 1890, 1895, 1896])

    def test_field_mapping_matches_the_spec(self):
        ep = self.by_number[1896]
        self.assertEqual(ep["guid"], "1896.noagendanotes.com")
        self.assertEqual(ep["raw_guid"], "http://1896.noagendanotes.com")
        self.assertEqual(ep["title_raw"], '1896 - "Just Dew It"')
        self.assertEqual(ep["title_display"], "Just Dew It")
        self.assertEqual(ep["link_url"], "http://1896.noagendanotes.com")
        self.assertEqual(ep["duration_sec"], 9292)
        self.assertIn("na-1896-art-feed.jpg", ep["artwork_url"])
        self.assertEqual(ep["published_at"].isoformat(), "2026-08-20T20:46:44+00:00")

    def test_no_description_is_carried_into_the_parsed_fields(self):
        # Episode 1890's item in the fixture carries a description blob.
        for ep in self.episodes:
            for value in ep.values():
                self.assertNotIn("Executive Producers", str(value))

    def test_guest_host_role_is_captured(self):
        self.assertEqual(self.by_number[1896]["feed_guest_hosts"], ["Rob Dew"])

    def test_plain_host_role_is_never_captured(self):
        # The feed lists John C Dvorak as `role="host"` on every item, including
        # 1889 -- the producer tribute to him -- and on every episode published
        # since. That role is a boilerplate template value; ingesting it would
        # print his name as host of episodes he was not on.
        for ep in self.episodes:
            self.assertNotIn("John C Dvorak", ep["feed_guest_hosts"])
            self.assertNotIn("Adam Curry", ep["feed_guest_hosts"])
        self.assertEqual(self.by_number[1889]["feed_guest_hosts"], [])

    def test_namespace_prefixes_are_not_hardcoded(self):
        # This feed's `podcast:` namespace URI is the GitHub docs URL, not the
        # canonical podcastindex.org one. Elements are matched by local name,
        # so an arbitrary prefix and URI still parse.
        xml = b"""<?xml version="1.0"?>
        <rss xmlns:zz="urn:whatever" xmlns:qq="urn:itunes-ish" version="2.0"><channel>
          <item>
            <title>1900 - "Renamed Namespaces"</title>
            <link>http://1900.noagendanotes.com</link>
            <guid isPermaLink="true">http://1900.noagendanotes.com</guid>
            <pubDate>Sun, 30 Aug 2026 21:00:00 +0000</pubDate>
            <qq:image href="https://example.com/art.jpg"/>
            <qq:duration>3600</qq:duration>
            <zz:person role="guest host">Someone New</zz:person>
          </item>
        </channel></rss>"""
        episodes, failures = parse_feed(xml)
        self.assertEqual(failures, [])
        self.assertEqual(episodes[0]["duration_sec"], 3600)
        self.assertEqual(episodes[0]["artwork_url"], "https://example.com/art.jpg")
        self.assertEqual(episodes[0]["feed_guest_hosts"], ["Someone New"])

    def test_missing_channel_raises(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<?xml version="1.0"?><rss version="2.0"></rss>')
