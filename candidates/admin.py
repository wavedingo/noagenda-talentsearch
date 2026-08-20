from django.contrib import admin

from .models import Candidate, Demo


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("stage_name", "user", "status", "is_featured", "created_at")
    list_filter = ("status", "is_featured")
    search_fields = ("stage_name", "user__email")


@admin.register(Demo)
class DemoAdmin(admin.ModelAdmin):
    list_display = ("candidate", "status", "duration_sec", "created_at")
    list_filter = ("status",)
