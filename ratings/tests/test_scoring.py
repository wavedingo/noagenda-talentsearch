from django.test import SimpleTestCase

from ratings.scoring import PRIOR_SEED, appearance_score, composite, smooth


class SmoothTests(SimpleTestCase):
    def test_no_votes_returns_the_prior(self):
        self.assertEqual(smooth(5, 0, 10, 3.5), 3.5)

    def test_equal_votes_and_m_is_the_midpoint(self):
        # v=m=10 → half the raw mean, half the prior.
        self.assertEqual(smooth(5, 10, 10, 3.5), 4.25)

    def test_many_votes_approach_the_raw_mean(self):
        self.assertAlmostEqual(smooth(5, 10_000, 10, 3.5), 5, places=2)

    def test_m_demo_matches_the_display_threshold(self):
        from ratings.scoring import M_DEMO

        self.assertEqual(M_DEMO, 10)

    def test_seed_prior_is_three_point_five(self):
        self.assertEqual(PRIOR_SEED, 3.5)


class AppearanceScoreTests(SimpleTestCase):
    def test_unweighted_mean(self):
        self.assertEqual(appearance_score([4.0, 2.0]), 3.0)

    def test_one_weak_night_does_not_drop_the_candidate(self):
        # Four nights, one 2.0: mean is 4.25, not "discarded" and not dominating.
        self.assertEqual(appearance_score([5.0, 5.0, 5.0, 2.0]), 4.25)

    def test_no_appearances_is_none_not_zero(self):
        self.assertIsNone(appearance_score([]))


class CompositeTests(SimpleTestCase):
    def test_default_weights(self):
        self.assertAlmostEqual(composite(5, 3, 0.7, 0.3), 4.4)

    def test_weights_are_not_renormalized(self):
        self.assertEqual(composite(5, 1, 1, 0), 5)
