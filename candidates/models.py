from django.core.files.storage import default_storage
from django.db import models

from accounts.models import User


class RejectionReason(models.TextChoices):
    """Canned reasons (spec 3.2). The message a candidate actually receives is
    in `REJECTION_MESSAGES` -- these labels are the moderator-facing shorthand."""

    AUDIO_QUALITY = "audio_quality", "Audio quality"
    NOT_AN_AUDITION = "not_an_audition", "Not an audition demo"
    HOUSE_RULES = "house_rules", "Breaks the house rules"
    IMPERSONATION = "impersonation", "Identity not verified"
    DUPLICATE = "duplicate", "Duplicate submission"
    OTHER = "other", "Other"


# Written for a fellow producer having a bad day, not as a status code
# (spec principle 3). Every one of these ends with a way forward.
REJECTION_MESSAGES = {
    RejectionReason.AUDIO_QUALITY: (
        "We couldn't get a clear enough listen to judge this one — the recording came "
        "through too quiet, too distorted, or too noisy. A quieter room and a closer "
        "microphone usually fixes it, and you're welcome to send another take."
    ),
    RejectionReason.NOT_AN_AUDITION: (
        "This doesn't seem to be an audition demo. We're after a few minutes of you "
        "hosting — reacting to a story, running a segment, whatever shows how you'd "
        "sound on the show. Send one over whenever you're ready."
    ),
    RejectionReason.HOUSE_RULES: (
        "This one falls outside the house rules for the site. Nothing personal, and "
        "you're welcome to submit something else."
    ),
    RejectionReason.IMPERSONATION: (
        "We weren't able to confirm that this profile belongs to the person it names. "
        "If that's a mistake, reply to this email and we'll sort it out."
    ),
    RejectionReason.DUPLICATE: (
        "This looks like a duplicate of something already submitted, so we've closed "
        "it out. Your other submission is unaffected."
    ),
    RejectionReason.OTHER: (
        "We're not able to publish this one. If you'd like more detail, reply to this "
        "email and we'll explain."
    ),
}


class RejectableMixin(models.Model):
    """Shared rejection copy for the two things a moderator can turn down."""

    class Meta:
        abstract = True

    @property
    def rejection_message(self):
        if not self.rejection_reason:
            return ""
        text = REJECTION_MESSAGES.get(self.rejection_reason, REJECTION_MESSAGES[RejectionReason.OTHER])
        return f"{text}\n\n{self.rejection_note}" if self.rejection_note else text


class Candidate(RejectableMixin):
    """One audition profile per account (spec 3.2).

    `stage_name`, `bio` and `photo_path` hold the **approved** copy -- they are
    the only fields a public template ever reads. Once a candidate is live,
    their edits land in the `pending_*` columns and the public page keeps
    showing the approved version until a moderator promotes the draft, so there
    is no window in which unapproved text is public and no way for a candidate
    to pull their own page down mid-review by editing it. A candidate who is not
    yet live has no approved copy to protect, so their edits go straight to the
    main fields and reset the status to `pending`.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LIVE = "live", "Live"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"
        BANNED = "banned", "Banned"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="candidate")
    # Assigned once at creation and never re-derived from stage_name: this is a
    # URL people paste around, and a rename must not break existing links.
    slug = models.SlugField(max_length=110, unique=True)
    stage_name = models.CharField(max_length=100)
    bio = models.TextField(max_length=1500, blank=True)
    photo_path = models.CharField(max_length=500, blank=True)

    pending_stage_name = models.CharField(max_length=100, blank=True)
    pending_bio = models.TextField(max_length=1500, blank=True)
    pending_photo_path = models.CharField(max_length=500, blank=True)
    pending_submitted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_featured = models.BooleanField(default=False)
    rejection_reason = models.CharField(max_length=30, choices=RejectionReason.choices, blank=True)
    rejection_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.stage_name

    @property
    def is_public(self):
        return self.status == self.Status.LIVE

    @property
    def has_pending_edit(self):
        return self.pending_submitted_at is not None

    @property
    def photo_url(self):
        return default_storage.url(self.photo_path) if self.photo_path else ""

    @property
    def pending_photo_url(self):
        return default_storage.url(self.pending_photo_path) if self.pending_photo_path else ""

    @property
    def live_demo(self):
        return self.demos.filter(status=Demo.Status.LIVE).order_by("-created_at").first()

    @property
    def current_demo(self):
        """The demo the candidate is working with, live or not -- everything
        except the archived history."""
        return self.demos.exclude(status=Demo.Status.ARCHIVED).order_by("-created_at").first()


class Demo(RejectableMixin):
    """An uploaded audition tape.

    Two independent axes, deliberately not collapsed into one field:
    `status` is what a moderator decided, `processing_state` is what the
    transcode pipeline did. A demo is publicly playable only when it is both
    `live` and `ready`.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        LIVE = "live", "Live"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class ProcessingState(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="demos")
    # Never served: the original still carries whatever ID3 tags, cover art and
    # authoring software the uploader's machine wrote into it. Kept under the
    # `private/` key prefix for moderation and appeals only.
    original_path = models.CharField(max_length=500)
    stream_path = models.CharField(max_length=500, blank=True)
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    processing_state = models.CharField(
        max_length=20, choices=ProcessingState.choices, default=ProcessingState.QUEUED
    )
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True)

    rejection_reason = models.CharField(max_length=30, choices=RejectionReason.choices, blank=True)
    rejection_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Demo({self.candidate.stage_name}, {self.status})"

    @property
    def is_ready(self):
        return self.processing_state == self.ProcessingState.READY

    @property
    def is_playable(self):
        return self.is_ready and bool(self.stream_path)

    @property
    def is_public(self):
        return self.status == self.Status.LIVE and self.is_playable

    @property
    def stream_url(self):
        return default_storage.url(self.stream_path) if self.stream_path else ""

    @property
    def duration_display(self):
        if not self.duration_sec:
            return ""
        minutes, seconds = divmod(self.duration_sec, 60)
        return f"{minutes}:{seconds:02d}"
