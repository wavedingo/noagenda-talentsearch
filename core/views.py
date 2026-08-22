from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from episodes.models import Episode
from ratings.services import community_favorites, rising_demos

from .settings_util import get_setting


HOME_EPISODE_COUNT = 3
HOME_FAVORITE_COUNT = 4


def home(request):
    favorites = community_favorites()[:HOME_FAVORITE_COUNT]
    # Rising Demos stand in until someone has been tagged on an episode, so
    # the home page isn't an empty "community favorites" heading.
    rising = [] if favorites else rising_demos()[:HOME_FAVORITE_COUNT]
    return render(
        request,
        "core/home.html",
        {
            "latest_episodes": Episode.objects.prefetch_related("appearances").all()[:HOME_EPISODE_COUNT],
            "favorites": favorites,
            "rising": rising,
            "auditions_open": get_setting("auditions_open"),
        },
    )


def about(request):
    return render(
        request,
        "core/about.html",
        {"vote_eligibility_hours": get_setting("vote_eligibility_hours")},
    )


def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})


def _test_500(request):
    raise Exception("intentional test error")
