from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from candidates.tests.helpers import make_user
from ratings.eligibility import blast_radius, waiting_queryset


class BlastRadiusTests(TestCase):
    def test_zero_hours_means_nobody_is_waiting(self):
        make_user("new@example.com")
        self.assertEqual(waiting_queryset(0).count(), 0)

    def test_lowering_the_delay_makes_older_accounts_eligible(self):
        now = timezone.now()
        waiting = make_user("wait@example.com")
        waiting.created_at = now - timedelta(hours=24)
        waiting.save(update_fields=["created_at"])
        old_enough = make_user("ok@example.com")
        old_enough.created_at = now - timedelta(hours=60)
        old_enough.save(update_fields=["created_at"])
        blast = blast_radius(48, 12, now=now)
        self.assertEqual(blast["waiting_before"], 1)
        self.assertEqual(blast["newly_eligible"], 1)
        self.assertEqual(blast["newly_gated"], 0)
