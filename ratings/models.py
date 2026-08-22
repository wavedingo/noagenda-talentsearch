from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from candidates.models import Candidate
from episodes.models import Episode


class Appearance(models.Model):
    """A guest-host slot on an episode (spec 3.5).

    `candidate` is nullable so a moderator can tag a feed-declared name (Rob Dew
    on 1896) before that person has a profile here. Ratings key on this row, so
    linking a candidate later is an UPDATE — no vote migration. `guest_name` is
    always stored, as a snapshot, so the appearance still has a name if the
    candidate is later unlinked.
    """

    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, related_name="appearances")
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appearances",
    )
    guest_name = models.CharField(max_length=100, default="")
    admin_note = models.CharField(max_length=500, blank=True)
    rateable_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    rating_avg = models.FloatField(null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)
    smoothed_score = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["episode", "candidate"],
                condition=Q(candidate__isnull=False),
                name="unique_episode_candidate",
            ),
            models.UniqueConstraint(
                fields=["episode", "guest_name"],
                name="unique_episode_guest_name",
            ),
        ]

    def __str__(self):
        return f"{self.display_name} on {self.episode.episode_number}"

    @property
    def display_name(self):
        if self.candidate_id:
            return self.candidate.stage_name
        return self.guest_name

    @property
    def is_rateable(self):
        return timezone.now() <= self.rateable_until


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
            models.UniqueConstraint(
                fields=["user", "rateable_type", "rateable_id"], name="unique_user_rateable"
            )
        ]
        indexes = [
            models.Index(fields=["rateable_type", "rateable_id"], name="rating_rateable_idx"),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.rateable_type}:{self.rateable_id} ({self.stars})"
