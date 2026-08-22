from datetime import timedelta

from django.utils import timezone

from .models import Rating

RATINGS_PER_MINUTE = 30


def rating_rate_limited(user):
    if not user.is_authenticated:
        return False
    window_start = timezone.now() - timedelta(seconds=60)
    return (
        Rating.objects.filter(user=user, updated_at__gte=window_start).count()
        >= RATINGS_PER_MINUTE
    )
