from django.contrib import admin

from .models import Episode


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("episode_number", "title_display", "published_at")
    search_fields = ("title_display", "guid")
