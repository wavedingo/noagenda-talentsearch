from django.db import models

from accounts.models import User


class Candidate(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LIVE = "live", "Live"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        BANNED = "banned", "Banned"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="candidate")
    stage_name = models.CharField(max_length=100)
    bio = models.TextField(max_length=1500, blank=True)
    photo_path = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.stage_name


class Demo(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LIVE = "live", "Live"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="demos")
    original_path = models.CharField(max_length=500)
    stream_path = models.CharField(max_length=500, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Demo({self.candidate.stage_name}, {self.status})"
