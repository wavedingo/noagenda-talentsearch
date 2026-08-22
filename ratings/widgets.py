from .eligibility import is_vote_eligible, vote_eligible_at
from .models import Rating
from .services import public_rating_summary

STAR_VALUES = (1, 2, 3, 4, 5)


def build_widget(user, rateable_type, obj, user_stars=None):
    if rateable_type == Rating.RateableType.DEMO:
        closed = not obj.is_public
        closed_copy = ""
    else:
        closed = not obj.is_rateable
        closed_copy = "Ratings for this appearance are closed."

    authenticated = user.is_authenticated
    eligible = is_vote_eligible(user) if authenticated else False
    return {
        "rateable_type": rateable_type,
        "rateable_id": obj.pk,
        "stars": STAR_VALUES,
        "user_stars": user_stars,
        "summary": public_rating_summary(obj),
        "closed": closed,
        "closed_copy": closed_copy,
        "login_required": not authenticated,
        "eligible": eligible,
        "eligible_at": vote_eligible_at(user) if authenticated and not eligible else None,
        "can_rate": authenticated and eligible and not closed,
    }
