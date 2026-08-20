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
    enclosure_url = models.URLField(max_length=500, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.episode_number} - {self.title_display}"
