from datetime import timedelta

from django.utils import timezone

from .models import MagicLink, User

EMAIL_LINK_LIMIT_PER_HOUR = 3
IP_LINK_LIMIT_PER_HOUR = 10
IP_SIGNUP_LIMIT_PER_DAY = 5


def email_link_requests_exceeded(email):
    window_start = timezone.now() - timedelta(hours=1)
    count = MagicLink.objects.filter(user__email=email, created_at__gte=window_start).count()
    return count >= EMAIL_LINK_LIMIT_PER_HOUR


def ip_link_requests_exceeded(ip):
    if not ip:
        return False
    window_start = timezone.now() - timedelta(hours=1)
    count = MagicLink.objects.filter(requested_ip=ip, created_at__gte=window_start).count()
    return count >= IP_LINK_LIMIT_PER_HOUR


def ip_signup_limit_exceeded(ip):
    if not ip:
        return False
    window_start = timezone.now() - timedelta(days=1)
    count = User.objects.filter(signup_ip=ip, created_at__gte=window_start).count()
    return count >= IP_SIGNUP_LIMIT_PER_DAY
