from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from candidates.models import Candidate
from episodes.models import Episode

from .settings_util import get_setting


HOME_EPISODE_COUNT = 3
HOME_CANDIDATE_COUNT = 4


def home(request):
    live_candidates = Candidate.objects.filter(status=Candidate.Status.LIVE).order_by(
        "-approved_at", "-created_at"
    )
    return render(
        request,
        "core/home.html",
        {
            "latest_episodes": Episode.objects.all()[:HOME_EPISODE_COUNT],
            "latest_candidates": live_candidates[:HOME_CANDIDATE_COUNT],
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
