from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from episodes.models import Episode
from ratings.services import attach_demo_summaries, community_favorites, rising_demos

from .settings_util import get_setting


HOME_EPISODE_COUNT = 3
HOME_FAVORITE_COUNT = 4


def home(request):
    favorites = community_favorites()[:HOME_FAVORITE_COUNT]
    # Rising Demos stand in until someone has been tagged on an episode, so
    # the home page isn't an empty "community favorites" heading.
    rising = [] if favorites else rising_demos()[:HOME_FAVORITE_COUNT]

    # "Currently leading" is always the top Rising Demo -- the best-rated tape
    # among candidates who have *not* been on the show yet. That keeps it
    # complementary to the board below rather than a copy of its first cell:
    # once guest hosts exist the board becomes Community Favorites and this
    # still shows who is coming up behind them.
    leading = attach_demo_summaries(rising_demos()[:1])
    return render(
        request,
        "core/home.html",
        {
            "latest_episodes": Episode.objects.prefetch_related("appearances").all()[:HOME_EPISODE_COUNT],
            "favorites": attach_demo_summaries(favorites),
            "rising": attach_demo_summaries(rising),
            "leading": leading[0] if leading else None,
            "auditions_open": get_setting("auditions_open"),
        },
    )


def about(request):
    return render(
        request,
        "core/about.html",
        {"vote_eligibility_hours": get_setting("vote_eligibility_hours")},
    )


def resources(request):
    """Recording help for producers who have never made an audio file.

    Deliberately not in the site nav (there is one link to it, from the demo
    upload box on the Audition page) -- it is help at the moment of need, not
    a section of the site.
    """
    return render(request, "core/resources.html")


def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})


def _test_500(request):
    raise Exception("intentional test error")
