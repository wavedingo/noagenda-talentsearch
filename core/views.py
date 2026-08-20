from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from .settings_util import get_setting


def home(request):
    return render(request, "core/home.html")


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
