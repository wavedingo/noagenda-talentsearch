from django.contrib import admin

from .models import MagicLink, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "display_name", "role", "created_at", "banned_at", "deleted_at")
    list_filter = ("role",)
    search_fields = ("email", "display_name")
    readonly_fields = ("created_at",)


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "requested_ip", "expires_at", "used_at", "created_at")
    readonly_fields = ("token_hash", "created_at")
