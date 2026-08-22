"""Rating writes, appearance tagging, and denormalized score refresh.

Public views and the admin tagging screen call these so "rate" and "tag" mean
one thing each. Ranking math lives in scoring.py; this module is the ORM
around it.
"""

from datetime import timedelta

from django.db.models import Avg, Count

from candidates.models import Candidate, Demo
from core.settings_util import get_setting
from moderation.models import AdminAuditLog

from .eligibility import is_vote_eligible, vote_eligible_at
from .models import Appearance, Rating
from .scoring import (
    M_APPEARANCE,
    M_DEMO,
    PRIOR_SEED,
    appearance_score,
    composite,
    smooth,
)


class RatingError(Exception):
    """User-facing: why this rating was not recorded."""


class TagError(Exception):
    """User-facing: why this appearance was not tagged."""


def countable_ratings():
    """Ratings that feed public averages and the scoring job.

    Banned accounts are excluded (spec 3.7). Deleted-but-not-banned accounts
    still count: deletion anonymizes, it does not unwind the aggregate (3.1).
    """
    return Rating.objects.filter(user__banned_at__isnull=True)


def public_rating_summary(obj, threshold=None):
    """Average and count for public copy, or None below the display threshold.

    None means the template prints "Not enough ratings yet" — never 0.0.
    """
    if threshold is None:
        threshold = int(get_setting("min_votes_to_display"))
    if obj.rating_count < threshold or obj.rating_avg is None:
        return None
    return {"average": obj.rating_avg, "count": obj.rating_count}


def submit_rating(user, rateable_type, rateable_id, stars):
    if stars not in (1, 2, 3, 4, 5):
        raise RatingError("Ratings are 1 to 5 stars.")
    if not is_vote_eligible(user):
        when = vote_eligible_at(user)
        raise RatingError(
            f"New accounts wait a little before rating. You can rate from "
            f"{when.strftime('%d %b %Y, %H:%M')} UTC."
        )

    obj = _resolve_rateable(rateable_type, rateable_id)
    rating, created = Rating.objects.update_or_create(
        user=user,
        rateable_type=rateable_type,
        rateable_id=obj.pk,
        defaults={"stars": int(stars)},
    )
    refresh_item_aggregates(rateable_type, obj.pk)
    recompute_scores()
    return rating, created


def _resolve_rateable(rateable_type, rateable_id):
    if rateable_type == Rating.RateableType.DEMO:
        demo = Demo.objects.filter(pk=rateable_id).select_related("candidate").first()
        if demo is None or not demo.is_public:
            raise RatingError("That demo isn't available to rate.")
        return demo
    if rateable_type == Rating.RateableType.APPEARANCE:
        appearance = Appearance.objects.filter(pk=rateable_id).select_related("episode", "candidate").first()
        if appearance is None:
            raise RatingError("That appearance isn't available to rate.")
        if not appearance.is_rateable:
            raise RatingError("Ratings for this appearance are closed.")
        return appearance
    raise RatingError("That isn't something we can rate.")


def refresh_item_aggregates(rateable_type, rateable_id):
    agg = countable_ratings().filter(rateable_type=rateable_type, rateable_id=rateable_id).aggregate(
        v=Count("id"), r=Avg("stars")
    )
    count = agg["v"] or 0
    avg = float(agg["r"]) if agg["r"] is not None else None
    if rateable_type == Rating.RateableType.DEMO:
        Demo.objects.filter(pk=rateable_id).update(rating_count=count, rating_avg=avg)
    elif rateable_type == Rating.RateableType.APPEARANCE:
        Appearance.objects.filter(pk=rateable_id).update(rating_count=count, rating_avg=avg)


def tag_appearance(episode, actor, *, candidate=None, guest_name="", admin_note=""):
    guest_name = (guest_name or "").strip()
    if candidate is None and not guest_name:
        raise TagError("Name a guest host or pick a candidate.")
    if candidate is not None:
        guest_name = guest_name or candidate.stage_name
        if Appearance.objects.filter(episode=episode, candidate=candidate).exists():
            raise TagError(f"{candidate.stage_name} is already tagged on this episode.")
    if Appearance.objects.filter(episode=episode, guest_name=guest_name).exists():
        raise TagError(f"{guest_name} is already tagged on this episode.")

    days = int(get_setting("appearance_rating_window_days"))
    appearance = Appearance.objects.create(
        episode=episode,
        candidate=candidate,
        guest_name=guest_name,
        admin_note=admin_note.strip(),
        rateable_until=episode.published_at + timedelta(days=days),
    )
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action="appearance.tag",
        target_type="appearance",
        target_id=appearance.pk,
        metadata_json={
            "episode_id": episode.pk,
            "episode_number": episode.episode_number,
            "guest_name": guest_name,
            "candidate_id": candidate.pk if candidate else None,
        },
    )
    recompute_scores()
    return appearance


def link_candidate(appearance, candidate, actor):
    if appearance.candidate_id:
        raise TagError("This appearance is already linked to a candidate.")
    if Appearance.objects.filter(episode=appearance.episode, candidate=candidate).exists():
        raise TagError(f"{candidate.stage_name} is already tagged on this episode.")
    appearance.candidate = candidate
    appearance.save(update_fields=["candidate"])
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action="appearance.link",
        target_type="appearance",
        target_id=appearance.pk,
        metadata_json={"candidate_id": candidate.pk, "guest_name": appearance.guest_name},
    )
    recompute_scores()
    return appearance


def untag_appearance(appearance, actor):
    """Remove an appearance and the ratings on it.

    Untagging is a deliberate admin action, not a side effect of anything else.
    Ratings key on this row, so they have to go with it or they orphan.
    """
    pk = appearance.pk
    Rating.objects.filter(
        rateable_type=Rating.RateableType.APPEARANCE, rateable_id=pk
    ).delete()
    appearance.delete()
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action="appearance.untag",
        target_type="appearance",
        target_id=pk,
        metadata_json={"guest_name": appearance.guest_name, "episode_id": appearance.episode_id},
    )
    recompute_scores()


def recompute_scores():
    """Write denormalized averages, smoothed scores, and composites.

    Live candidates only receive composite scores. Item-level averages are
    refreshed for every demo and appearance so admin analytics stay current.
    """
    demo_stats = _stats_by_id(Rating.RateableType.DEMO)
    appearance_stats = _stats_by_id(Rating.RateableType.APPEARANCE)

    live_demo_ids = list(Demo.objects.filter(status=Demo.Status.LIVE).values_list("pk", flat=True))
    c_demos = _prior(Rating.RateableType.DEMO, live_demo_ids)
    appearance_ids = list(Appearance.objects.values_list("pk", flat=True))
    c_appearances = _prior(Rating.RateableType.APPEARANCE, appearance_ids)

    weight_appearance = float(get_setting("score_weight_appearance"))
    weight_demo = float(get_setting("score_weight_demo"))

    for demo in Demo.objects.all().iterator():
        v, r = demo_stats.get(demo.pk, (0, None))
        demo.rating_count = v
        demo.rating_avg = r
        demo.smoothed_score = smooth(r if r is not None else c_demos, v, M_DEMO, c_demos)
        demo.save(update_fields=["rating_count", "rating_avg", "smoothed_score", "updated_at"])

    appearances = list(Appearance.objects.select_related("candidate").all())
    for appearance in appearances:
        v, r = appearance_stats.get(appearance.pk, (0, None))
        appearance.rating_count = v
        appearance.rating_avg = r
        appearance.smoothed_score = smooth(
            r if r is not None else c_appearances, v, M_APPEARANCE, c_appearances
        )
        appearance.save(update_fields=["rating_count", "rating_avg", "smoothed_score"])

    scores_by_candidate = {}
    for appearance in appearances:
        if not appearance.candidate_id:
            continue
        scores_by_candidate.setdefault(appearance.candidate_id, []).append(appearance.smoothed_score)

    live_demos = {
        demo.candidate_id: demo
        for demo in Demo.objects.filter(status=Demo.Status.LIVE).order_by("created_at")
    }

    Candidate.objects.exclude(status=Candidate.Status.LIVE).update(
        demo_score=None, appearance_score=None, composite_score=None
    )

    for candidate in Candidate.objects.filter(status=Candidate.Status.LIVE).iterator():
        live_demo = live_demos.get(candidate.pk)
        demo_s = live_demo.smoothed_score if live_demo is not None else c_demos
        app_s = appearance_score(scores_by_candidate.get(candidate.pk, []))
        candidate.demo_score = demo_s
        candidate.appearance_score = app_s
        candidate.composite_score = (
            composite(app_s, demo_s, weight_appearance, weight_demo) if app_s is not None else None
        )
        candidate.save(update_fields=["demo_score", "appearance_score", "composite_score", "updated_at"])


def _stats_by_id(rateable_type):
    rows = (
        countable_ratings()
        .filter(rateable_type=rateable_type)
        .values("rateable_id")
        .annotate(v=Count("id"), r=Avg("stars"))
    )
    return {
        row["rateable_id"]: (row["v"], float(row["r"]) if row["r"] is not None else None) for row in rows
    }


def _prior(rateable_type, rateable_ids):
    if not rateable_ids:
        return PRIOR_SEED
    agg = countable_ratings().filter(
        rateable_type=rateable_type, rateable_id__in=rateable_ids
    ).aggregate(r=Avg("stars"))
    if agg["r"] is None:
        return PRIOR_SEED
    return float(agg["r"])


def load_user_stars(user, rateable_type, ids):
    if not user.is_authenticated or not ids:
        return {}
    return dict(
        Rating.objects.filter(
            user=user, rateable_type=rateable_type, rateable_id__in=ids
        ).values_list("rateable_id", "stars")
    )


def leaderboard_size():
    return int(get_setting("leaderboard_size"))


def community_favorites():
    size = leaderboard_size()
    return list(
        Candidate.objects.filter(status=Candidate.Status.LIVE, composite_score__isnull=False)
        .order_by("-composite_score", "-approved_at")[:size]
    )


def rising_demos():
    size = leaderboard_size()
    return list(
        Candidate.objects.filter(status=Candidate.Status.LIVE, composite_score__isnull=True)
        .order_by("-demo_score", "-approved_at")[:size]
    )
