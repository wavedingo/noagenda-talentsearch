from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.models import Settings


class HealthzTests(TestCase):
    def test_healthz_returns_200_with_db_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class HomeTests(TestCase):
    def test_home_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_home_shows_action_buttons_and_updated_copy(self):
        response = self.client.get("/")
        self.assertContains(response, "The producer-driven audition for the show's next guest-host.")
        self.assertContains(response, "Rate guest appearances")
        self.assertContains(response, reverse("episodes:list"))
        self.assertContains(response, reverse("candidates:list"))
        self.assertNotContains(response, "Log out")

    def test_discover_talent_survives_an_empty_board(self):
        """It lives on the Currently leading card, which only renders when a
        rising demo exists -- so the empty state has to keep it or the button
        disappears from the home page entirely."""
        response = self.client.get("/")
        self.assertNotContains(response, "Currently leading")
        self.assertContains(response, "Discover Talent")
        self.assertContains(response, "Not a vote")


class BrandingTests(TestCase):
    def test_header_logo_and_favicons_are_linked(self):
        response = self.client.get("/")
        self.assertContains(response, 'class="site-logo"')
        self.assertContains(response, 'rel="icon"')
        self.assertContains(response, "/static/img/favicon.svg")
        self.assertContains(response, "/static/img/og-image.png")

    def test_logo_is_decorative_beside_the_wordmark(self):
        """The header pairs the mark with "No Agenda / Talent Search" as real
        text, so the image is alt="" -- otherwise the link's accessible name
        says the site's name twice."""
        response = self.client.get("/")
        self.assertContains(response, 'class="site-logo" src="/static/img/logo-light.svg" alt=""')
        self.assertContains(response, "site-wordmark-kicker")
        self.assertContains(response, "Talent Search")

    def test_ticker_renders_and_is_hidden_from_assistive_tech(self):
        """The ticker is a bumper sticker, not navigation. It also has to be
        duplicated exactly for the -50% marquee loop to be seamless."""
        response = self.client.get("/")
        self.assertContains(response, 'class="marquee" aria-hidden="true"')
        self.assertContains(response, "Troll room is listening", count=2)

    def test_not_a_vote_is_a_page_module_never_a_ticker_phrase(self):
        """A slogan scrolling past in a bumper loop trivialises the one thing
        the site most needs people to believe."""
        response = self.client.get("/")
        html = response.content.decode()
        self.assertNotIn('marquee-item">Not a vote', html)
        self.assertIn("Not a vote", html)

    def test_footer_is_present_on_every_page(self):
        for path in ("/", "/candidates/", "/episodes/", "/about/", "/leaderboard/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, "Producers advise. The show decides.")
                self.assertContains(response, "site-footer-mark")

    def test_branding_is_dark_only(self):
        """The site has no light theme (refresh decision 3), so the logo and
        touch icon are the light-on-dark pair unconditionally -- nothing is
        selected by prefers-color-scheme any more."""
        response = self.client.get("/")
        self.assertContains(response, "/static/img/logo-light.svg")
        self.assertNotContains(response, "/static/img/logo-dark.svg")
        self.assertContains(response, "/static/img/apple-touch-icon-light.png")
        self.assertNotContains(response, "/static/img/apple-touch-icon-dark.png")
        self.assertNotContains(response, "prefers-color-scheme")
        self.assertContains(response, '<meta name="color-scheme" content="dark">')

    def test_self_hosted_fonts_are_linked_and_google_is_not_called(self):
        """Decision 12: faces are served from our own origin. Reverting to
        Google Fonts is deliberate work, not something that creeps back in."""
        response = self.client.get("/")
        self.assertContains(response, "/static/css/fonts.css")
        self.assertNotContains(response, "fonts.googleapis.com")
        self.assertNotContains(response, "fonts.gstatic.com")


class AboutTests(TestCase):
    def test_about_returns_200(self):
        response = self.client.get("/about/")
        self.assertEqual(response.status_code, 200)

    def test_about_renders_the_compact_and_keeps_its_reasoning(self):
        """Renamed from "House Rules" -- rules is the wrong register for a
        voluntary compact. The paragraphs stay: the mock compressed each one
        to a single line, and the reasoning is the part doing the work."""
        response = self.client.get("/about/")
        self.assertContains(response, "The compact")
        self.assertContains(response, 'id="the-compact"')
        self.assertNotContains(response, "House Rules")
        self.assertContains(response, "Nobody survives that comparison")
        self.assertContains(response, "Low ratings are allowed. Cruelty is not.")

    def test_about_keeps_the_sections_the_mock_dropped(self):
        """The mock's About loses the demo-tape checklist, the only takedown
        address on the site, and the closing thanks. All three are kept."""
        response = self.client.get("/about/")
        self.assertContains(response, "Who should audition")
        self.assertContains(response, "Sounds like a")
        self.assertContains(response, "hello@noagendatalentsearch.com")
        self.assertContains(response, "Thank you for courage.")

    def test_about_links_to_the_recording_help_page(self):
        response = self.client.get("/about/")
        self.assertContains(response, reverse("core:resources"))
        self.assertContains(response, "If you need help with recording audio")

    def test_about_points_reports_at_the_in_product_route_and_email(self):
        """Rule 7 names both ways to raise a problem. "Report this profile" is
        a real control on every candidate page, so the copy has to keep
        matching it."""
        response = self.client.get("/about/")
        self.assertContains(response, "Report this profile")
        self.assertContains(response, "hello@noagendatalentsearch.com")

    def test_home_links_to_the_compact_anchor(self):
        response = self.client.get("/")
        self.assertContains(response, "/about/#the-compact")

    def test_about_renders_live_vote_eligibility_hours_not_hardcoded(self):
        cache.clear()
        Settings.objects.filter(key="vote_eligibility_hours").update(value_json=12)
        response = self.client.get("/about/")
        self.assertContains(response, "12 hours after signup")
        self.assertNotContains(response, "48 hours after signup")

    def test_about_says_accounts_can_rate_immediately_when_delay_is_off(self):
        cache.clear()
        Settings.objects.filter(key="vote_eligibility_hours").update(value_json=0)
        response = self.client.get("/about/")
        self.assertContains(response, "as soon as they sign in")
        self.assertNotContains(response, "0 hours after signup")


class PolaroidTests(TestCase):
    def test_tilt_is_stable_for_a_slug_and_varies_between_slugs(self):
        """The wall must not twitch as you page through it, and the filter has
        to agree across processes -- hash() is salted per interpreter, so a
        card would lean differently on each worker."""
        from core.templatetags.stagecraft import tilt

        self.assertEqual(tilt("dana-whitlock"), tilt("dana-whitlock"))
        self.assertNotEqual(tilt("dana-whitlock"), tilt("priya-raman"))
        self.assertEqual(tilt(""), "0deg")

    def test_tilt_stays_inside_the_design_span(self):
        from core.templatetags.stagecraft import TILT_SPAN, tilt

        for slug in ("a", "big-sister-mo", "the-night-shift", "z" * 40):
            with self.subTest(slug=slug):
                self.assertLessEqual(abs(float(tilt(slug).removesuffix("deg"))), TILT_SPAN)


class ResourcesTests(TestCase):
    def test_resources_page_renders(self):
        response = self.client.get("/resources/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "we've got your back")
        self.assertContains(response, "audacityteam.org")
        self.assertContains(response, "currycaster")

    def test_external_links_are_safe_and_open_in_a_new_tab(self):
        """Every link here leaves the site, so none of them may hand the
        destination a window.opener handle back to us."""
        response = self.client.get("/resources/")
        html = response.content.decode()
        external = html.count('href="http')
        self.assertEqual(external, html.count('rel="noopener noreferrer"'))
        self.assertEqual(external, html.count('target="_blank"'))

    def test_resources_is_reachable_from_the_demo_upload_box_but_not_the_nav(self):
        """Help at the moment of need. It is deliberately absent from the
        header -- a producer meets it when they are staring at the file
        picker, not as a section of the site."""
        home = self.client.get("/")
        self.assertNotContains(home, "/resources/")
