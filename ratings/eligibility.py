"""Vote-eligibility gate (spec 4.1).

Computed at request time from the live setting, never frozen at signup. A
moderator raising the delay re-gates accounts that have not yet voted; it does
not touch ratings already cast.
"""

from datetime import timedelta

from django.utils import timezone

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
