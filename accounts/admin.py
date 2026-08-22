from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from candidates.admin import ModeratorVisibleAdmin
from ratings.models import Rating

from .models import MagicLink, User
from .services import ban_user, set_role, unban_user


@admin.register(User)
class UserAdmin(ModeratorVisibleAdmin):
    list_display = ("email", "display_name", "role", "created_at", "banned_at", "deleted_at")
    list_filter = ("role",)
    search_fields = ("email", "display_name")
    readonly_fields = ("created_at", "email_verified_at", "deleted_at", "signup_ip", "banned_at")
    fields = (
        "email",
        "display_name",
        "role",
        "vote_eligible_override_at",
        "banned_at",
        "deleted_at",
        "signup_ip",
        "created_at",
        "email_verified_at",
    )
    change_form_template = "admin/accounts/user/change_form.html"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            readonly.extend(["email", "display_name", "role", "vote_eligible_override_at"])
        return readonly

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def get_urls(self):
        return [
            path(
                "<path:object_id>/action/",
                self.admin_site.admin_view(self.user_action_view),
                name="accounts_user_action",
            ),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["ratings"] = list(
            Rating.objects.filter(user_id=object_id).order_by("-updated_at")[:100]
        )
        extra_context["can_moderate_user"] = request.user.is_superuser
        extra_context["roles"] = User.Role.choices
        return super().change_view(request, object_id, form_url, extra_context)

    @method_decorator(require_POST)
    def user_action_view(self, request, object_id):
        if not request.user.is_superuser:
            messages.error(request, "Only an admin can ban accounts or change roles.")
            return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
        user = User.objects.get(pk=object_id)
        action = request.POST.get("action")
        if action == "ban":
            ban_user(user, request.user)
            messages.success(request, f"{user.email} is banned. Their ratings no longer count.")
        elif action == "unban":
            unban_user(user, request.user)
            messages.success(request, f"{user.email} is unbanned. Any profile is withdrawn.")
        elif action == "set_role":
            role = request.POST.get("role")
            try:
                set_role(user, role, request.user)
            except ValueError:
                messages.error(request, "Unknown role.")
            else:
                messages.success(request, f"{user.email} is now {user.get_role_display()}.")
        return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "requested_ip", "expires_at", "used_at", "created_at")
    readonly_fields = ("token_hash", "created_at")
