from django.contrib import admin, messages
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from . import services, tasks
from .forms import ModerationDecisionForm
from .models import Candidate, Demo, RejectionReason


class ModeratorVisibleAdmin(admin.ModelAdmin):
    """Lets moderators see (but not edit) the things they moderate.

    `User.has_perm` grants only admins, so without this a moderator logs in and
    finds an empty dashboard — no way to reach the queue they exist to work.
    Approve and reject go through the queue's own POST endpoints, not through
    the model form, so read-only is the correct level of access here.
    """

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Candidate)
class CandidateAdmin(ModeratorVisibleAdmin):
    list_display = ("stage_name", "user", "status", "has_pending_edit", "is_featured", "created_at")
    list_filter = ("status", "is_featured")
    search_fields = ("stage_name", "slug", "user__email")
    readonly_fields = ("created_at", "updated_at", "approved_at", "pending_submitted_at")
    change_list_template = "admin/candidates/candidate/change_list.html"

    @admin.display(boolean=True, description="Edit pending")
    def has_pending_edit(self, obj):
        return obj.has_pending_edit

    def get_urls(self):
        return [
            path(
                "queue/",
                self.admin_site.admin_view(self.queue_view),
                name="candidates_moderation_queue",
            ),
            path(
                "queue/decide/",
                self.admin_site.admin_view(self.decide_view),
                name="candidates_moderation_decide",
            ),
            path(
                "queue/process-demos/",
                self.admin_site.admin_view(self.process_demos_view),
                name="candidates_process_demos",
            ),
            path(
                "rankings/",
                self.admin_site.admin_view(self.rankings_view),
                name="candidates_rankings",
            ),
        ] + super().get_urls()

    def queue_view(self, request):
        """The moderation queue (spec 4.1): pending candidates, pending profile
        edits, and demos awaiting review with an inline player."""
        pending_candidates = Candidate.objects.filter(status=Candidate.Status.PENDING).order_by("created_at")
        pending_edits = Candidate.objects.filter(pending_submitted_at__isnull=False).order_by(
            "pending_submitted_at"
        )
        # Only `ready` demos reach the queue: moderators approve by listening,
        # and the thing they listen to is the transcoded copy.
        pending_demos = (
            Demo.objects.filter(
                status=Demo.Status.PENDING, processing_state=Demo.ProcessingState.READY
            )
            .select_related("candidate", "candidate__user")
            .order_by("created_at")
        )
        stuck_demos = (
            Demo.objects.filter(
                status=Demo.Status.PENDING,
                processing_state__in=[Demo.ProcessingState.QUEUED, Demo.ProcessingState.PROCESSING],
            )
            .select_related("candidate")
            .order_by("created_at")
        )
        failed_demos = (
            Demo.objects.filter(processing_state=Demo.ProcessingState.FAILED)
            .exclude(status=Demo.Status.ARCHIVED)
            .select_related("candidate")
            .order_by("created_at")
        )
        context = {
            **self.admin_site.each_context(request),
            "title": "Moderation queue",
            "pending_candidates": pending_candidates,
            "pending_edits": pending_edits,
            "pending_demos": pending_demos,
            "stuck_demos": stuck_demos,
            "failed_demos": failed_demos,
            "rejection_reasons": RejectionReason.choices,
            "opts": self.model._meta,
        }
        return render(request, "admin/candidates/moderation_queue.html", context)

    @method_decorator(require_POST)
    def decide_view(self, request):
        form = ModerationDecisionForm(request.POST)
        if not form.is_valid():
            self.message_user(request, _first_error(form), level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))

        data = form.cleaned_data
        approve = data["action"] == "approve"
        reason, note = data.get("reason", ""), data.get("note", "")

        if data["target"] == "demo":
            demo = get_object_or_404(Demo, pk=data["target_id"])
            if approve:
                services.approve_demo(demo, request.user)
                message = f"Demo from {demo.candidate.stage_name} is live."
            else:
                services.reject_demo(demo, request.user, reason, note)
                message = f"Demo from {demo.candidate.stage_name} rejected; the candidate has been emailed."
        else:
            candidate = get_object_or_404(Candidate, pk=data["target_id"])
            if data["target"] == "profile_edit":
                if approve:
                    services.approve_profile_edit(candidate, request.user)
                    message = f"Profile edit for {candidate.stage_name} published."
                else:
                    services.reject_profile_edit(candidate, request.user, reason, note)
                    message = f"Profile edit for {candidate.stage_name} discarded; their live profile is unchanged."
            elif approve:
                services.approve_candidate(candidate, request.user)
                message = f"{candidate.stage_name} is live."
            else:
                services.reject_candidate(candidate, request.user, reason, note)
                message = f"{candidate.stage_name} rejected; the candidate has been emailed."

        self.message_user(request, message, level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))

    @method_decorator(require_POST)
    def process_demos_view(self, request):
        """Run the transcode backstop by hand (see candidates/tasks.py)."""
        processed, failed = tasks.drain_queue()
        self.message_user(
            request,
            f"Processed {processed} demo(s); {failed} failed.",
            level=messages.WARNING if failed else messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))

    def rankings_view(self, request):
        """Full rankings with raw vs. smoothed scores (spec 4). Public pages
        never get this list — only the top N by composite."""
        live = Candidate.objects.filter(status=Candidate.Status.LIVE).order_by(
            F("composite_score").desc(nulls_last=True),
            F("demo_score").desc(nulls_last=True),
            "stage_name",
        )
        context = {
            **self.admin_site.each_context(request),
            "title": "Full rankings",
            "candidates": live,
            "opts": self.model._meta,
        }
        return render(request, "admin/candidates/rankings.html", context)


@admin.register(Demo)
class DemoAdmin(ModeratorVisibleAdmin):
    list_display = ("candidate", "status", "processing_state", "duration_display", "created_at")
    list_filter = ("status", "processing_state")
    search_fields = ("candidate__stage_name", "candidate__user__email")
    readonly_fields = (
        "original_path",
        "stream_path",
        "duration_sec",
        "file_size",
        "processing_state",
        "processing_started_at",
        "processed_at",
        "processing_error",
        "created_at",
        "updated_at",
        "approved_at",
        "player",
    )

    @admin.display(description="Player")
    def player(self, obj):
        if not obj.is_playable:
            return "—"
        return format_html('<audio controls preload="none" src="{}"></audio>', obj.stream_url)


def _first_error(form):
    for errors in form.errors.values():
        return errors[0]
    return "That decision couldn't be recorded."
