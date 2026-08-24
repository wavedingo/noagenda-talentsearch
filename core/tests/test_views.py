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
        self.assertContains(response, "Rate Guest Appearances")
        self.assertContains(response, "Discover Talent")
        self.assertContains(response, reverse("episodes:list"))
        self.assertContains(response, reverse("candidates:list"))
        self.assertNotContains(response, "Log out")


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
        self.assertNotContains(response, "Not a vote")

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

    def test_about_renders_house_rules(self):
        response = self.client.get("/about/")
        self.assertContains(response, "House Rules")

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
