"""Audition operations shared by the public views and the moderation queue.

Kept out of both so the moderation queue and a future management command take
exactly the same code path — approval must mean one thing, not two.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core.settings_util import get_setting
from moderation.models import AdminAuditLog

from . import emails, storage, tasks
from .audio import DemoValidationError, inspect_demo, uploaded_to_tempfile
from .images import process_photo
from .models import Candidate, Demo

# Pulled forward from Phase 5's rate limits (spec 8): this is the first
# authenticated endpoint that accepts 50 MB and spawns an ffmpeg process.
MAX_DEMO_UPLOADS_PER_DAY = 5

SLUG_FALLBACK = "candidate"


def build_slug(stage_name):
    """A URL-safe, unique slug. Assigned once and never re-derived — this is a
    link people paste around, and a rename must not break it."""
    base = slugify(stage_name)[:100] or SLUG_FALLBACK
    slug = base
    suffix = 2
    while Candidate.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"[:110]
        suffix += 1
    return slug


def save_profile(user, stage_name, bio, photo_file=None, clear_photo=False):
    """Create or update the audition profile for `user`.

    A live candidate's edits land in the `pending_*` columns and the public page
    keeps showing the approved copy until a moderator promotes the draft.
    Everyone else edits the main fields directly, which returns them to
    `pending` — they have no approved copy to protect.
    """
    candidate = Candidate.objects.filter(user=user).first()
    new_photo_path = ""
    if photo_file is not None:
        new_photo_path = storage.save_bytes(
            storage.photo_path(storage.new_key()), process_photo(photo_file)
        )

    if candidate is None:
        return Candidate.objects.create(
            user=user,
            slug=build_slug(stage_name),
            stage_name=stage_name,
            bio=bio,
            photo_path=new_photo_path,
            status=Candidate.Status.PENDING,
        )

    if candidate.status == Candidate.Status.LIVE:
        candidate.pending_stage_name = stage_name
        candidate.pending_bio = bio
        if new_photo_path:
            storage.delete(candidate.pending_photo_path)
            candidate.pending_photo_path = new_photo_path
        elif clear_photo:
            storage.delete(candidate.pending_photo_path)
            candidate.pending_photo_path = ""
        candidate.pending_submitted_at = timezone.now()
    else:
        candidate.stage_name = stage_name
        candidate.bio = bio
        if new_photo_path:
            storage.delete(candidate.photo_path)
            candidate.photo_path = new_photo_path
        elif clear_photo:
            storage.delete(candidate.photo_path)
            candidate.photo_path = ""
        candidate.status = Candidate.Status.PENDING
        candidate.rejection_reason = ""
        candidate.rejection_note = ""
    candidate.save()
    return candidate


def upload_quota_exceeded(candidate):
    window_start = timezone.now() - timedelta(days=1)
    return candidate.demos.filter(created_at__gte=window_start).count() >= MAX_DEMO_UPLOADS_PER_DAY


def submit_demo(candidate, uploaded_file):
    """Validate an upload, store the original, and queue the transcode.

    Raises DemoValidationError with a message meant for the uploader. Validation
    happens in-request so a bad file is rejected while they're still looking at
    the form; the transcode is what runs in the background.
    """
    if upload_quota_exceeded(candidate):
        raise DemoValidationError(
            f"You've uploaded {MAX_DEMO_UPLOADS_PER_DAY} demos today, which is the daily limit. "
            "Try again tomorrow, or email hello@noagendatalentsearch.com if you're stuck."
        )

    max_mb = int(get_setting("demo_max_file_mb"))
    if uploaded_file.size > max_mb * 1024 * 1024:
        raise DemoValidationError(
            f"That file is {uploaded_file.size / (1024 * 1024):.0f} MB and the limit is {max_mb} MB. "
            "Exporting at a lower bitrate usually brings it well under."
        )
    if not uploaded_file.name.lower().endswith(".mp3"):
        raise DemoValidationError("Demos need to be an MP3 file.")

    max_duration = int(get_setting("demo_max_duration_sec"))
    key = storage.new_key()
    with uploaded_to_tempfile(uploaded_file) as temp_path:
        duration = inspect_demo(temp_path, max_duration)
        original_path = storage.save_local_file(storage.demo_original_path(key), temp_path)

    with transaction.atomic():
        # A new demo is a new rating slate (spec 3.2). Ratings stay attached to
        # the archived row -- Rating.rateable_id points at the demo -- so
        # archiving is the whole of "old ratings are archived".
        candidate.demos.exclude(status=Demo.Status.ARCHIVED).update(status=Demo.Status.ARCHIVED)
        demo = Demo.objects.create(
            candidate=candidate,
            original_path=original_path,
            duration_sec=duration,
            file_size=uploaded_file.size,
            status=Demo.Status.PENDING,
            processing_state=Demo.ProcessingState.QUEUED,
        )

    transaction.on_commit(lambda: tasks.dispatch(demo))
    return demo


def withdraw(candidate):
    candidate.status = Candidate.Status.WITHDRAWN
    candidate.save(update_fields=["status", "updated_at"])
    return candidate


def reopen(candidate):
    """Un-withdraw. Back to `pending`, not straight to `live` — the profile has
    to pass moderation again before it reappears."""
    candidate.status = Candidate.Status.PENDING
    candidate.save(update_fields=["status", "updated_at"])
    return candidate


# --- Moderation ------------------------------------------------------------


def approve_candidate(candidate, actor):
    candidate.status = Candidate.Status.LIVE
    candidate.approved_at = timezone.now()
    candidate.rejection_reason = ""
    candidate.rejection_note = ""
    candidate.save(update_fields=["status", "approved_at", "rejection_reason", "rejection_note", "updated_at"])
    _audit(actor, "candidate.approve", candidate)
    emails.send_candidate_approved(candidate)
    return candidate


def reject_candidate(candidate, actor, reason, note=""):
    candidate.status = Candidate.Status.REJECTED
    candidate.rejection_reason = reason
    candidate.rejection_note = note
    candidate.save(update_fields=["status", "rejection_reason", "rejection_note", "updated_at"])
    _audit(actor, "candidate.reject", candidate, reason=reason)
    emails.send_candidate_rejected(candidate, reason, note)
    return candidate


def approve_profile_edit(candidate, actor):
    """Promote a live candidate's pending draft into the public fields."""
    candidate.stage_name = candidate.pending_stage_name or candidate.stage_name
    candidate.bio = candidate.pending_bio
    if candidate.pending_photo_path:
        storage.delete(candidate.photo_path)
        candidate.photo_path = candidate.pending_photo_path
    _clear_pending_edit(candidate)
    candidate.save()
    _audit(actor, "candidate.approve_edit", candidate)
    return candidate


def reject_profile_edit(candidate, actor, reason, note=""):
    """Discard the draft. The approved profile is untouched and stays live."""
    storage.delete(candidate.pending_photo_path)
    _clear_pending_edit(candidate)
    candidate.save()
    _audit(actor, "candidate.reject_edit", candidate, reason=reason)
    emails.send_profile_edit_rejected(candidate, reason, note)
    return candidate


def _clear_pending_edit(candidate):
    candidate.pending_stage_name = ""
    candidate.pending_bio = ""
    candidate.pending_photo_path = ""
    candidate.pending_submitted_at = None


def approve_demo(demo, actor):
    demo.status = Demo.Status.LIVE
    demo.approved_at = timezone.now()
    demo.rejection_reason = ""
    demo.rejection_note = ""
    demo.save(update_fields=["status", "approved_at", "rejection_reason", "rejection_note", "updated_at"])
    _audit(actor, "demo.approve", demo)
    emails.send_demo_approved(demo)
    return demo


def reject_demo(demo, actor, reason, note=""):
    demo.status = Demo.Status.REJECTED
    demo.rejection_reason = reason
    demo.rejection_note = note
    demo.save(update_fields=["status", "rejection_reason", "rejection_note", "updated_at"])
    _audit(actor, "demo.reject", demo, reason=reason)
    emails.send_demo_rejected(demo, reason, note)
    return demo


def _audit(actor, action, target, **metadata):
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action=action,
        target_type=target.__class__.__name__.lower(),
        target_id=target.pk,
        metadata_json=metadata,
    )
