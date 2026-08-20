from django.contrib import admin

from .models import AdminAuditLog, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "target_type", "target_id", "reason", "status", "created_at")
    list_filter = ("status", "reason")


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("admin_user", "action", "target_type", "target_id", "created_at")
    readonly_fields = ("admin_user", "action", "target_type", "target_id", "metadata_json", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
