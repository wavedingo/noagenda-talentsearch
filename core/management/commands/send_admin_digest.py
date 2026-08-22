"""Daily operator email: signups, queue depth, RSS health, vote spikes."""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from candidates.models import Candidate, Demo
from episodes.models import FeedSyncRun
from ratings.analytics import spike_candidates


def build_digest(now=None):
    now = now or timezone.now()
    since = now - timedelta(hours=24)
    signups = User.objects.filter(created_at__gte=since, deleted_at__isnull=True).count()
    pending_candidates = Candidate.objects.filter(status=Candidate.Status.PENDING).count()
    pending_edits = Candidate.objects.filter(pending_submitted_at__isnull=False).count()
    pending_demos = Demo.objects.filter(
        status=Demo.Status.PENDING, processing_state=Demo.ProcessingState.READY
    ).count()
    hidden = Candidate.objects.filter(hidden_at__isnull=False).count()
    last_sync = FeedSyncRun.objects.order_by("-started_at").first()
    failures = FeedSyncRun.consecutive_failures()
    spikes = spike_candidates(now)
    lines = [
        f"Signups in the last 24 hours: {signups}",
        f"Pending candidates: {pending_candidates}",
        f"Pending profile edits: {pending_edits}",
        f"Demos waiting on a listen: {pending_demos}",
        f"Auto-hidden profiles: {hidden}",
        f"RSS consecutive failures: {failures}",
    ]
    if last_sync:
        lines.append(
            f"Last RSS sync: {last_sync.status} at {last_sync.started_at:%Y-%m-%d %H:%M} UTC"
            + (f" — {last_sync.error}" if last_sync.error else "")
        )
    else:
        lines.append("Last RSS sync: none recorded")
    if spikes:
        lines.append("Vote-velocity spikes:")
        for row in spikes:
            lines.append(
                f"  - {row['candidate'].stage_name}: {row['last_24h']} ratings in 24h "
                f"({row['last_7d']} in 7d)"
            )
    else:
        lines.append("Vote-velocity spikes: none")
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Email the daily admin digest to ADMIN_NOTIFY_EMAIL."

    def handle(self, *args, **options):
        body = build_digest()
        send_mail(
            subject="No Agenda Talent Search — daily digest",
            message=body,
            from_email=settings.MAIL_FROM,
            recipient_list=[settings.ADMIN_NOTIFY_EMAIL],
        )
        self.stdout.write(self.style.SUCCESS(f"Digest sent to {settings.ADMIN_NOTIFY_EMAIL}"))
