from django.contrib import admin

from candidates.admin import ModeratorVisibleAdmin

from .models import Appearance, Rating


@admin.register(Appearance)
class AppearanceAdmin(ModeratorVisibleAdmin):
    list_display = ("display_name", "episode", "candidate", "rateable_until", "rating_count", "smoothed_score")
    search_fields = ("guest_name", "candidate__stage_name", "episode__title_display")
    readonly_fields = ("created_at", "rating_avg", "rating_count", "smoothed_score")

    @admin.display(description="Name")
    def display_name(self, obj):
        return obj.display_name


@admin.register(Rating)
class RatingAdmin(ModeratorVisibleAdmin):
    list_display = ("user", "rateable_type", "rateable_id", "stars", "updated_at")
    list_filter = ("rateable_type", "stars")
    search_fields = ("user__email",)
