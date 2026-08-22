from django.contrib import admin

from candidates.admin import ModeratorVisibleAdmin
from episodes.models import Episode

from .models import Appearance, Rating


@admin.register(Appearance)
class AppearanceAdmin(ModeratorVisibleAdmin):
    list_display = ("display_name", "episode", "candidate", "rateable_until", "rating_count", "smoothed_score")
    search_fields = ("guest_name", "candidate__stage_name", "episode__title_display")
    readonly_fields = ("created_at", "rating_avg", "rating_count", "smoothed_score")
    change_list_template = "admin/ratings/appearance/change_list.html"

    @admin.display(description="Name")
    def display_name(self, obj):
        return obj.display_name

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["untagged_feed_hosts"] = [
            episode
            for episode in Episode.objects.prefetch_related("appearances").order_by("-published_at")
            if episode.feed_guest_hosts and not episode.appearances.all()
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Rating)
class RatingAdmin(ModeratorVisibleAdmin):
    list_display = ("user", "rateable_type", "rateable_id", "stars", "updated_at")
    list_filter = ("rateable_type", "stars")
    search_fields = ("user__email",)
