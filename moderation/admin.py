from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from candidates.admin import ModeratorVisibleAdmin
from candidates.models import Candidate
from moderation.models import AdminAuditLog, Report
from moderation.services import resolve_report


@admin.register(Report)
class ReportAdmin(ModeratorVisibleAdmin):
    list_display = ("reporter", "target_type", "target_id", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    change_list_template = "admin/moderation/report/change_list.html"

    def get_urls(self):
        return [
            path(
                "queue/",
                self.admin_site.admin_view(self.queue_view),
                name="moderation_reports_queue",
            ),
            path(
                "queue/decide/",
                self.admin_site.admin_view(self.decide_view),
                name="moderation_report_decide",
            ),
        ] + super().get_urls()

    def queue_view(self, request):
        open_reports = list(
            Report.objects.filter(status=Report.Status.OPEN)
            .select_related("reporter")
            .order_by("created_at")
        )
        candidate_ids = [r.target_id for r in open_reports if r.target_type == Report.TARGET_CANDIDATE]
        candidates = {c.pk: c for c in Candidate.objects.filter(pk__in=candidate_ids)}
        open_counts = {}
        for report in open_reports:
            open_counts[report.target_id] = open_counts.get(report.target_id, 0) + 1
        for report in open_reports:
            report.candidate = candidates.get(report.target_id)
            report.open_count = open_counts.get(report.target_id, 0)
        closed_reports = list(
            Report.objects.exclude(status=Report.Status.OPEN)
            .select_related("reporter")
            .order_by("-created_at")[:20]
        )
        for report in closed_reports:
            report.candidate = candidates.get(report.target_id) or Candidate.objects.filter(
                pk=report.target_id
            ).first()
        context = {
            **self.admin_site.each_context(request),
            "title": "Reports",
            "open_reports": open_reports,
            "closed_reports": closed_reports,
            "opts": self.model._meta,
        }
        return render(request, "admin/moderation/reports_queue.html", context)

    @method_decorator(require_POST)
    def decide_view(self, request):
        report = get_object_or_404(Report, pk=request.POST.get("report_id"))
        outcome = request.POST.get("outcome")
        if outcome not in (Report.Status.RESOLVED, Report.Status.DISMISSED):
            messages.error(request, "Unknown outcome.")
            return HttpResponseRedirect(reverse("admin:moderation_reports_queue"))
        resolve_report(report, request.user, outcome)
        messages.success(request, f"Report {outcome}.")
        return HttpResponseRedirect(reverse("admin:moderation_reports_queue"))


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("admin_user", "action", "target_type", "target_id", "created_at")
    readonly_fields = ("admin_user", "action", "target_type", "target_id", "metadata_json", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "admin_user__email")

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
