from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from core.settings_util import get_setting

from .models import Episode

EPISODES_PER_PAGE = 20  # spec B.5


def episode_list(request):
    episodes = Episode.objects.prefetch_related("appearances").all()
    page = Paginator(episodes, EPISODES_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "episodes/list.html",
        {"page_obj": page, "min_episode_number": get_setting("min_episode_number")},
    )


def episode_detail(request, number):
    # The episode number is derived/display-only (spec 3.4), so it isn't the
    # lookup key in the database -- but it is the stable, shareable thing to
    # put in a URL. Duplicates would be a feed bug; newest wins if one appears.
    episode = Episode.objects.filter(episode_number=number).order_by("-published_at").first()
    if episode is None:
        raise Http404("No such episode")
    return render(request, "episodes/detail.html", {"episode": episode})
