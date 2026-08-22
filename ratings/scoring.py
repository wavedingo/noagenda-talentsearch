"""Bayesian shrinkage for demo and appearance scores (spec 3.6).

Pure functions: no ORM, no settings, no I/O. The job in `recompute.py` is the
only place these meet the database. Spec §9 names this as one of the four
places a silent bug would hurt most — keep it that boring.
"""

PRIOR_SEED = 3.5
M_DEMO = 10
M_APPEARANCE = 5


def smooth(raw_mean, votes, m, prior):
    """Pull a low-vote mean toward `prior`.

    smooth(R, v, m, C) = (v/(v+m))·R + (m/(v+m))·C

    `votes == 0` returns the prior (the formula's own limit), so a candidate
    with a live demo and no ratings is comparable rather than missing.
    """
    votes = int(votes)
    if votes < 0:
        raise ValueError("votes cannot be negative")
    if m < 0:
        raise ValueError("m cannot be negative")
    if votes == 0:
        return float(prior)
    v = float(votes)
    return (v / (v + m)) * float(raw_mean) + (m / (v + m)) * float(prior)


def appearance_score(smoothed_appearances):
    """Unweighted mean of per-appearance smoothed scores.

    A candidate with four appearances is not penalized for one weak night, and
    each night still counts. An empty list is None — that candidate belongs on
    Rising Demos, not on the main board with a fabricated appearance score.
    """
    scores = list(smoothed_appearances)
    if not scores:
        return None
    return sum(scores) / len(scores)


def composite(appearance, demo, weight_appearance, weight_demo):
    """Weighted mix of the two smoothed scores.

    Weights are taken as stored. They default to 0.7 / 0.3; this function does
    not renormalize, so an admin who sets them to 1 and 0 gets exactly that.
    """
    return float(weight_appearance) * float(appearance) + float(weight_demo) * float(demo)
