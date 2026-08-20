from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import User
from candidates.models import Candidate
from episodes.models import Episode


class Appearance(models.Model):
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, related_name="appearances")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="appearances")
    admin_note = models.CharField(max_length=500, blank=True)
    rateable_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["episode", "candidate"], name="unique_episode_candidate")
        ]

    def __str__(self):
        return f"{self.candidate.stage_name} on {self.episode.episode_number}"


class Rating(models.Model):
    class RateableType(models.TextChoices):
        DEMO = "demo", "Demo"
        APPEARANCE = "appearance", "Appearance"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    rateable_type = models.CharField(max_length=20, choices=RateableType.choices)
    rateable_id = models.PositiveIntegerField()
    stars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "rateable_type", "rateable_id"], name="unique_user_rateable")
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.rateable_type}:{self.rateable_id} ({self.stars})"
