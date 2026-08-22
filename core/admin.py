from django.contrib import admin, messages

from candidates.admin import ModeratorVisibleAdmin
from moderation.models import AdminAuditLog

from .models import Settings
from .settings_util import set_setting

# Spec §4.1. Score weights and the episode floor are admin-only; everything
# else is a live operational lever a moderator may reach for.
ADMIN_ONLY_KEYS = frozenset(
    {
        "score_weight_appearance",
        "score_weight_demo",
        "min_episode_number",
    }
)

SETTING_HELP = {
    "vote_eligibility_hours": (
        "Hours after signup before an account can rate demos or appearances. "
        "0 turns the gate off — new accounts can vote immediately. "
        "Changing this does not delete votes already cast."
    ),
    "appearance_rating_window_days": (
        "How long an appearance stays rateable after the episode is published. "
        "This is a closing window, not a delay: tagging opens ratings immediately. "
        "Already-tagged appearances keep the window they were created with."
    ),
    "min_votes_to_display": "Public average is hidden until a demo or appearance has this many ratings.",
    "leaderboard_size": "How many names the public Favorites and Rising Demos lists show.",
    "auditions_open": "When false, new audition profiles cannot be created.",
    "demo_max_duration_sec": "Maximum demo length in seconds (default 900 = 15 minutes).",
    "demo_max_file_mb": "Maximum demo upload size in megabytes.",
    "score_weight_appearance": "Admin only. Share of the composite from on-show appearances (default 0.7).",
    "score_weight_demo": "Admin only. Share of the composite from the live demo (default 0.3).",
    "min_episode_number": "Admin only. Episodes below this number are not ingested or listed.",
}


@admin.register(Settings)
class SettingsAdmin(ModeratorVisibleAdmin):
    list_display = ("key", "value_json", "who_can_edit")
    search_fields = ("key",)
    ordering = ("key",)
    readonly_fields = ("key",)
    fields = ("key", "value_json")

    def has_change_permission(self, request, obj=None):
        if not (request.user.is_active and request.user.is_staff):
            return False
        if obj is None:
            return True
        if obj.key in ADMIN_ONLY_KEYS:
            return request.user.is_superuser
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Who can edit")
    def who_can_edit(self, obj):
        return "Admin only" if obj.key in ADMIN_ONLY_KEYS else "Moderator or admin"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is not None and "value_json" in form.base_fields:
            form.base_fields["value_json"].help_text = SETTING_HELP.get(obj.key, "")
        return form

    def save_model(self, request, obj, form, change):
        old = None
        if change:
            old = Settings.objects.filter(pk=obj.pk).values_list("value_json", flat=True).first()
        # Write through set_setting so this worker's get_setting() cache dies.
        set_setting(obj.key, obj.value_json)
        AdminAuditLog.objects.create(
            admin_user=request.user if request.user.is_authenticated else None,
            action="settings.change",
            target_type="settings",
            target_id=None,
            metadata_json={"key": obj.key, "old": old, "new": obj.value_json},
        )
        if obj.key == "vote_eligibility_hours" and obj.value_json == 0:
            self.message_user(
                request,
                "Vote delay is off. New accounts can rate immediately.",
                level=messages.WARNING,
            )
