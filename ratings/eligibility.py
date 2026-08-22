"""Vote-eligibility gate (spec 4.1).

Computed at request time from the live setting, never frozen at signup. A
moderator raising the delay re-gates accounts that have not yet voted; it does
not touch ratings already cast.
"""

from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from core.settings_util import get_setting


def vote_eligible_at(user):
    if user.vote_eligible_override_at is not None:
        return user.vote_eligible_override_at
    hours = int(get_setting("vote_eligibility_hours"))
    return user.created_at + timedelta(hours=hours)


def is_vote_eligible(user, now=None):
    if not user.is_authenticated or not user.is_active:
        return False
    now = now or timezone.now()
    return now >= vote_eligible_at(user)


def waiting_queryset(hours, now=None):
    """Accounts that would be gated at this delay. Used for blast-radius copy."""
    now = now or timezone.now()
    hours = int(hours)
    if hours <= 0:
        return User.objects.none()
    cutoff = now - timedelta(hours=hours)
    return User.objects.filter(
        banned_at__isnull=True,
        deleted_at__isnull=True,
        vote_eligible_override_at__isnull=True,
        created_at__gt=cutoff,
    )


def blast_radius(old_hours, new_hours, now=None):
    waiting_before = waiting_queryset(old_hours, now).count()
    waiting_after = waiting_queryset(new_hours, now).count()
    return {
        "waiting_before": waiting_before,
        "waiting_after": waiting_after,
        "newly_eligible": max(0, waiting_before - waiting_after),
        "newly_gated": max(0, waiting_after - waiting_before),
    }
