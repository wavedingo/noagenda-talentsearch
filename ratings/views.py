from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import RatingForm
from .ratelimit import rating_rate_limited
from .services import (
    RatingError,
    attach_demo_summaries,
    community_favorites,
    rising_demos,
    submit_rating,
)


def leaderboard(request):
    favorites = attach_demo_summaries(community_favorites())
    rising = attach_demo_summaries(rising_demos())
    return render(
        request,
        "ratings/leaderboard.html",
        {
            "favorites": favorites,
            "rising": rising,
            "has_appearances": bool(favorites),
        },
    )


@login_required
@require_POST
def rate(request):
    form = RatingForm(request.POST)
    next_url = _safe_next(request)
    if not form.is_valid():
        messages.error(request, "That rating could not be saved.")
        return redirect(next_url)
    if rating_rate_limited(request.user):
        messages.error(request, "That's too many ratings in a short span. Try again in a minute.")
        return redirect(next_url)
    data = form.cleaned_data
    try:
        _, created = submit_rating(
            request.user, data["rateable_type"], data["rateable_id"], data["stars"]
        )
    except RatingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Rating saved." if created else "Rating updated.")
    return redirect(next_url)


def _safe_next(request):
    candidates = [request.POST.get("next"), request.META.get("HTTP_REFERER")]
    for url in candidates:
        if url and url_has_allowed_host_and_scheme(
            url, allowed_hosts={request.get_host()}, require_https=False
        ):
            return url
    return reverse("core:home")
