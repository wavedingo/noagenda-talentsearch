from django.db import models


class Episode(models.Model):
    guid = models.CharField(max_length=255, unique=True)
    raw_guid = models.CharField(max_length=500)
    episode_number = models.PositiveIntegerField()
    title_raw = models.TextField()
    title_display = models.CharField(max_length=500)
    published_at = models.DateTimeField()
    link_url = models.URLField(max_length=500)
    artwork_url = models.URLField(max_length=500, blank=True)
    # Stored for provenance only. Never rendered and never fetched: the feed
    # wraps it in an OP3 analytics prefix, so any request through it registers
    # as a download in the show's own statistics (spec 3.4). Episode pages
    # link to `link_url` (the show notes page) instead.
    enclosure_url = models.URLField(max_length=500, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    # Names from `<podcast:person role="guest host">`. The feed's `host` role is
    # boilerplate and is never ingested -- see episodes/feed.py.
    feed_guest_hosts = models.JSONField(default=list, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.episode_number} - {self.title_display}"

    @property
    def duration_display(self):
        if not self.duration_sec:
            return ""
        hours, remainder = divmod(self.duration_sec, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m" if hours else f"{minutes}m"


class FeedSyncRun(models.Model):
    """One attempt at syncing the feed.

    Kept as its own table rather than a `settings` row so that table keeps
    meaning "admin-editable configuration". Consecutive-failure alerting (3.4)
    and the Phase 5 admin digest both read from here.
    """

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    items_seen = models.PositiveIntegerField(default=0)
    episodes_created = models.PositiveIntegerField(default=0)
    episodes_updated = models.PositiveIntegerField(default=0)
    items_below_floor = models.PositiveIntegerField(default=0)
    items_failed = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.status} @ {self.started_at:%Y-%m-%d %H:%M}"

    # Only ever compared against a threshold of 3; a window this size is more
    # than enough and keeps the query bounded as run history accumulates
    # (48 runs a day).
    FAILURE_WINDOW = 25

    @classmethod
    def consecutive_failures(cls):
        """Failed runs since the last success, counting back from now."""
        recent = cls.objects.order_by("-started_at").values_list("status", flat=True)[: cls.FAILURE_WINDOW]
        count = 0
        for status in recent:
            if status != cls.Status.FAILED:
                break
            count += 1
        return count
