"""Account-level admin actions and self-service deletion (spec 3.1, 3.7)."""

from django.utils import timezone

from candidates.models import Candidate
from candidates.services import withdraw
from moderation.models import AdminAuditLog
from ratings.services import recompute_scores

from .models import User


def ban_user(user, actor, note=""):
    if user.banned_at is not None:
        return user
    user.banned_at = timezone.now()
    user.save(update_fields=["banned_at"])
    candidate = Candidate.objects.filter(user=user).first()
    if candidate is not None:
        candidate.status = Candidate.Status.BANNED
        candidate.save(update_fields=["status", "updated_at"])
    recompute_scores()
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action="user.ban",
        target_type="user",
        target_id=user.pk,
        metadata_json={"note": note},
    )
    return user


def unban_user(user, actor):
    if user.banned_at is None:
        return user
    user.banned_at = None
    user.save(update_fields=["banned_at"])
    candidate = Candidate.objects.filter(user=user, status=Candidate.Status.BANNED).first()
    if candidate is not None:
        withdraw(candidate)
    recompute_scores()
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action="user.unban",
        target_type="user",
        target_id=user.pk,
        metadata_json={},
    )
    return user


def set_role(user, role, actor):
    if role not in User.Role.values:
        raise ValueError(f"Unknown role: {role}")
    old = user.role
    if old == role:
        return user
    user.role = role
    user.save(update_fields=["role"])
    AdminAuditLog.objects.create(
        admin_user=actor if getattr(actor, "pk", None) else None,
        action="user.role_change",
        target_type="user",
        target_id=user.pk,
        metadata_json={"old": old, "new": role},
    )
    return user


def delete_account(user):
    """Anonymize the row and take any public profile down. Ratings stay."""
    candidate = Candidate.objects.filter(user=user).first()
    if candidate is not None and candidate.status not in {
        Candidate.Status.BANNED,
        Candidate.Status.WITHDRAWN,
    }:
        withdraw(candidate)
    user.email = f"deleted-{user.id}@deleted.noagendatalentsearch.com"
    user.display_name = ""
    user.signup_ip = None
    user.deleted_at = timezone.now()
    user.save(update_fields=["email", "display_name", "signup_ip", "deleted_at"])
    return user
