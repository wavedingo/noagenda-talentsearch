"""Vote-velocity and votes-per-account (spec §4 item 3, §8)."""

from collections import Counter
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from candidates.models import Candidate, Demo
from ratings.models import Appearance, Rating

SPIKE_ABS = 20
SPIKE_RATIO = 3.0


def _windows(now=None):
    now = now or timezone.now()
    return {
        "6h": now - timedelta(hours=6),
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
    }


def _counts_by_candidate(since):
    """Roll demo + appearance ratings since `since` up to a candidate id."""
    demo_map = dict(
        Demo.objects.filter(status=Demo.Status.LIVE).values_list("pk", "candidate_id")
    )
    appearance_map = dict(
        Appearance.objects.filter(candidate_id__isnull=False).values_list("pk", "candidate_id")
    )
    tallies = Counter()
    demo_rows = (
        Rating.objects.filter(
            user__banned_at__isnull=True,
            rateable_type=Rating.RateableType.DEMO,
            updated_at__gte=since,
            rateable_id__in=list(demo_map),
        )
        .values("rateable_id")
        .annotate(n=Count("id"))
    )
    for row in demo_rows:
        candidate_id = demo_map.get(row["rateable_id"])
        if candidate_id:
            tallies[candidate_id] += row["n"]
    appearance_rows = (
        Rating.objects.filter(
            user__banned_at__isnull=True,
            rateable_type=Rating.RateableType.APPEARANCE,
            updated_at__gte=since,
            rateable_id__in=list(appearance_map),
        )
        .values("rateable_id")
        .annotate(n=Count("id"))
    )
    for row in appearance_rows:
        candidate_id = appearance_map.get(row["rateable_id"])
        if candidate_id:
            tallies[candidate_id] += row["n"]
    return tallies


def candidate_velocity(now=None):
    windows = _windows(now)
    counts_6h = _counts_by_candidate(windows["6h"])
    counts_24h = _counts_by_candidate(windows["24h"])
    counts_7d = _counts_by_candidate(windows["7d"])
    candidate_ids = set(counts_6h) | set(counts_24h) | set(counts_7d)
    candidates = {
        c.pk: c
        for c in Candidate.objects.filter(pk__in=candidate_ids, status=Candidate.Status.LIVE)
    }
    rows = []
    for pk, candidate in candidates.items():
        last_6h = counts_6h.get(pk, 0)
        last_24h = counts_24h.get(pk, 0)
        last_7d = counts_7d.get(pk, 0)
        daily_avg = last_7d / 7.0
        spiked = last_24h >= SPIKE_ABS and daily_avg > 0 and last_24h >= SPIKE_RATIO * daily_avg
        rows.append(
            {
                "candidate": candidate,
                "last_6h": last_6h,
                "last_24h": last_24h,
                "last_7d": last_7d,
                "spiked": spiked,
            }
        )
    rows.sort(key=lambda row: (-row["last_24h"], row["candidate"].stage_name))
    return rows


def spike_candidates(now=None):
    return [row for row in candidate_velocity(now) if row["spiked"]]


def votes_per_account_histogram():
    rows = (
        Rating.objects.filter(user__banned_at__isnull=True, user__deleted_at__isnull=True)
        .values("user_id")
        .annotate(n=Count("id"))
    )
    hist = Counter(row["n"] for row in rows)
    return sorted(hist.items())
