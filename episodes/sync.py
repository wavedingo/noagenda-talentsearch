"""Fetch the feed and upsert episodes (spec 3.4).

The invariant running through all of this: a bad fetch never destroys data.
Existing episode rows are only ever created or updated, never deleted -- the
feed is a rolling ~230-item window, so episodes scrolling out of it is normal
and means nothing about whether they happened.
"""

import logging

import requests
from django.db import transaction
from django.utils import timezone

from core.settings_util import get_setting

from .feed import parse_feed
from .models import Episode, FeedSyncRun

logger = logging.getLogger(__name__)

FEED_TIMEOUT_SECONDS = 30
USER_AGENT = "noagendatalentsearch.com feed sync (+https://noagendatalentsearch.com)"

# Log at ERROR from here on so the failure is loud rather than one more WARNING
# in the pile. The alert channel itself is the Phase 5 admin digest (A.8).
ALERT_AFTER_CONSECUTIVE_FAILURES = 3

FEED_FIELDS = (
    "raw_guid",
    "episode_number",
    "title_raw",
    "title_display",
    "published_at",
    "link_url",
    "artwork_url",
    "enclosure_url",
    "duration_sec",
    "feed_guest_hosts",
)


class FeedFetchError(Exception):
    """The feed could not be fetched or yielded nothing usable."""


def fetch_feed(url):
    try:
        response = requests.get(url, timeout=FEED_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        raise FeedFetchError(f"fetch failed: {exc}") from exc
    if response.status_code != 200:
        raise FeedFetchError(f"feed returned HTTP {response.status_code}")
    if not response.content:
        raise FeedFetchError("feed returned an empty body")
    return response.content


def sync_feed(url, dry_run=False):
    """Run one sync. Returns the FeedSyncRun row recording what happened."""
    run = FeedSyncRun(status=FeedSyncRun.Status.FAILED)
    if not dry_run:
        run.save()

    try:
        xml_bytes = fetch_feed(url)
        episodes, failures = parse_feed(xml_bytes)
    except Exception as exc:  # fetch failure, malformed XML, missing <channel>
        return _fail(run, str(exc), dry_run)

    run.items_seen = len(episodes) + len(failures)
    run.items_failed = len(failures)
    for title, reason in failures:
        logger.warning("rss_sync: skipping unparseable item %r: %s", title, reason)

    # An empty parse is a failure, not "the show deleted its archive".
    if not episodes:
        return _fail(run, "feed parsed to zero episodes", dry_run)

    floor = int(get_setting("min_episode_number"))
    eligible = []
    for fields in episodes:
        if fields["episode_number"] < floor:
            run.items_below_floor += 1
            continue
        eligible.append(fields)

    if not dry_run:
        with transaction.atomic():
            for fields in eligible:
                _, created = Episode.objects.update_or_create(
                    guid=fields["guid"],
                    defaults={key: fields[key] for key in FEED_FIELDS},
                )
                if created:
                    run.episodes_created += 1
                else:
                    run.episodes_updated += 1
    else:
        known = set(Episode.objects.filter(guid__in=[f["guid"] for f in eligible]).values_list("guid", flat=True))
        run.episodes_created = sum(1 for f in eligible if f["guid"] not in known)
        run.episodes_updated = len(eligible) - run.episodes_created

    run.status = FeedSyncRun.Status.SUCCESS
    run.finished_at = timezone.now()
    if not dry_run:
        run.save()

    logger.info(
        "rss_sync: %d items, %d created, %d updated, %d below floor %d, %d unparseable",
        run.items_seen,
        run.episodes_created,
        run.episodes_updated,
        run.items_below_floor,
        floor,
        run.items_failed,
    )
    return run


def _fail(run, error, dry_run):
    run.status = FeedSyncRun.Status.FAILED
    run.error = error
    run.finished_at = timezone.now()
    if not dry_run:
        run.save()

    consecutive = FeedSyncRun.consecutive_failures() if not dry_run else 1
    message = "rss_sync failed (%d consecutive): %s"
    if consecutive >= ALERT_AFTER_CONSECUTIVE_FAILURES:
        logger.error(message, consecutive, error)
    else:
        logger.warning(message, consecutive, error)
    return run
