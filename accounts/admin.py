from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "display_name", "role", "created_at", "banned_at", "deleted_at")
    list_filter = ("role",)
    search_fields = ("email", "display_name")
    readonly_fields = ("created_at",)
