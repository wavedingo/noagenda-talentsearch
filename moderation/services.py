"""Reports, auto-hide, and the audit helper they share (spec 3.7)."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from candidates.models import Candidate
from moderation.models import AdminAuditLog, Report

AUTO_HIDE_THRESHOLD = 10


class ReportError(ValidationError):
    pass


def file_report(user, candidate, reason, details=""):
    if not user.is_authenticated or not user.is_active:
        raise ReportError("Log in to report a profile.")
    if candidate.user_id == user.pk:
        raise ReportError("You can't report your own profile.")
    if not candidate.is_public and candidate.status != Candidate.Status.LIVE:
        raise ReportError("That profile isn't public.")

    report, created = Report.objects.update_or_create(
        reporter=user,
        target_type=Report.TARGET_CANDIDATE,
        target_id=candidate.pk,
        defaults={
            "reason": reason,
            "details": (details or "").strip(),
            "status": Report.Status.OPEN,
        },
    )
    _audit(
        user,
        "report.file",
        "candidate",
        candidate.pk,
        reason=reason,
        created=created,
    )
    refresh_auto_hide(candidate)
    return report, created


def resolve_report(report, actor, status):
    if status not in (Report.Status.RESOLVED, Report.Status.DISMISSED):
        raise ReportError("Unknown report outcome.")
    report.status = status
    report.save(update_fields=["status", "updated_at"])
    action = "report.resolve" if status == Report.Status.RESOLVED else "report.dismiss"
    _audit(actor, action, report.target_type, report.target_id, report_id=report.pk)
    candidate = Candidate.objects.filter(pk=report.target_id).first()
    if candidate is not None:
        refresh_auto_hide(candidate)
    return report


def open_report_count(candidate):
    return Report.objects.filter(
        target_type=Report.TARGET_CANDIDATE,
        target_id=candidate.pk,
        status=Report.Status.OPEN,
    ).count()


def refresh_auto_hide(candidate):
    """Hide or unhide from the unique-open-report count. Status stays live."""
    count = open_report_count(candidate)
    if count >= AUTO_HIDE_THRESHOLD and candidate.hidden_at is None:
        candidate.hidden_at = timezone.now()
        candidate.save(update_fields=["hidden_at", "updated_at"])
        _audit(None, "candidate.auto_hide", "candidate", candidate.pk, open_reports=count)
    elif count < AUTO_HIDE_THRESHOLD and candidate.hidden_at is not None:
        candidate.hidden_at = None
        candidate.save(update_fields=["hidden_at", "updated_at"])
        _audit(None, "candidate.unhide", "candidate", candidate.pk, open_reports=count)
    return candidate


def _audit(actor, action, target_type, target_id, **metadata):
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata,
    )
