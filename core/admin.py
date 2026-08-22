from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from candidates.admin import ModeratorVisibleAdmin
from core.settings_util import get_setting, set_setting
from moderation.models import AdminAuditLog
from ratings.eligibility import blast_radius, waiting_queryset

from .models import Settings

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


def apply_vote_delay(request, new_hours):
    old = get_setting("vote_eligibility_hours")
    set_setting("vote_eligibility_hours", new_hours)
    AdminAuditLog.objects.create(
        admin_user=request.user if request.user.is_authenticated else None,
        action="settings.change",
        target_type="settings",
        target_id=None,
        metadata_json={"key": "vote_eligibility_hours", "old": old, "new": new_hours},
    )
    blast = blast_radius(old, new_hours)
    if new_hours == 0:
        messages.warning(request, "Vote delay is off. New accounts can rate immediately.")
    else:
        messages.success(
            request,
            f"Vote delay is now {new_hours} hours. "
            f"{blast['newly_eligible']} accounts became eligible; "
            f"{blast['newly_gated']} were re-gated.",
        )


@admin.register(Settings)
class SettingsAdmin(ModeratorVisibleAdmin):
    list_display = ("key", "value_json", "who_can_edit")
    search_fields = ("key",)
    ordering = ("key",)
    readonly_fields = ("key",)
    fields = ("key", "value_json")

    def get_urls(self):
        return [
            path(
                "vote-delay/",
                self.admin_site.admin_view(self.vote_delay_view),
                name="core_vote_delay",
            ),
        ] + super().get_urls()

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
            help_text = SETTING_HELP.get(obj.key, "")
            if obj.key == "vote_eligibility_hours":
                waiting = waiting_queryset(obj.value_json).count()
                help_text += f" {waiting} accounts are currently waiting."
            form.base_fields["value_json"].help_text = help_text
        return form

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if (
            request.method == "POST"
            and obj is not None
            and obj.key == "vote_eligibility_hours"
            and request.POST.get("confirm") != "1"
        ):
            new_value = _parse_json_int(request.POST.get("value_json"))
            if new_value is not None and new_value != obj.value_json:
                return render(
                    request,
                    "admin/core/vote_delay_confirm.html",
                    {
                        **self.admin_site.each_context(request),
                        "title": "Confirm vote delay change",
                        "opts": self.model._meta,
                        "old": obj.value_json,
                        "new": new_value,
                        "blast": blast_radius(obj.value_json, new_value),
                        "cancel_url": request.path,
                    },
                )
        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        old = None
        if change:
            old = Settings.objects.filter(pk=obj.pk).values_list("value_json", flat=True).first()
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

    def vote_delay_view(self, request):
        if request.method != "POST":
            return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))
        if not (request.user.is_active and request.user.is_staff):
            messages.error(request, "You cannot change that setting.")
            return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))
        try:
            new_hours = int(request.POST.get("hours"))
        except (TypeError, ValueError):
            messages.error(request, "Vote delay has to be a number of hours.")
            return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))
        if new_hours < 0 or new_hours > 336:
            messages.error(request, "Vote delay has to be between 0 and 336 hours.")
            return HttpResponseRedirect(reverse("admin:candidates_moderation_queue"))
        old = get_setting("vote_eligibility_hours")
        next_url = request.POST.get("next") or reverse("admin:candidates_moderation_queue")
        if request.POST.get("confirm") != "1" and new_hours != old:
            return render(
                request,
                "admin/core/vote_delay_confirm.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Confirm vote delay change",
                    "opts": self.model._meta,
                    "old": old,
                    "new": new_hours,
                    "blast": blast_radius(old, new_hours),
                    "next": next_url,
                    "cancel_url": next_url,
                },
            )
        apply_vote_delay(request, new_hours)
        return HttpResponseRedirect(next_url)


def _parse_json_int(raw):
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
