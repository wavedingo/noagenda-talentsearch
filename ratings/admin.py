from django.contrib import admin

from .models import Appearance, Rating


@admin.register(Appearance)
class AppearanceAdmin(admin.ModelAdmin):
    list_display = ("candidate", "episode", "rateable_until")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "rateable_type", "rateable_id", "stars", "updated_at")
    list_filter = ("rateable_type", "stars")
