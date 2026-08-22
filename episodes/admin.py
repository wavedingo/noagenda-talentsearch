from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from candidates.models import Candidate
from ratings.forms import TagAppearanceForm
from ratings.models import Appearance
from ratings.services import TagError, link_candidate, tag_appearance, untag_appearance

from .models import Episode, FeedSyncRun
from .sync import sync_feed


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = (
        "episode_number",
        "title_display",
        "published_at",
        "guest_hosts_display",
        "appearances_link",
        "synced_at",
    )
    search_fields = ("title_display", "title_raw", "guid")
    ordering = ("-published_at",)
    # Everything here is written by the sync job; hand-edits would be
    # overwritten on the next run.
    readonly_fields = [f.name for f in Episode._meta.fields]
    change_list_template = "admin/episodes/episode/change_list.html"

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    @admin.display(description="Guest hosts (from feed)")
    def guest_hosts_display(self, obj):
        return ", ".join(obj.feed_guest_hosts) or "—"

    @admin.display(description="Appearances")
    def appearances_link(self, obj):
        url = reverse("admin:episodes_tag_appearances", args=[obj.pk])
        count = getattr(obj, "appearance_count", obj.appearances.count())
        return format_html('<a href="{}">{} tagged</a>', url, count)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(appearance_count=Count("appearances"))

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [
            path(
                "resync/",
                self.admin_site.admin_view(self.resync_view),
                name="episodes_episode_resync",
            ),
            path(
                "<path:object_id>/appearances/",
                self.admin_site.admin_view(self.appearances_view),
                name="episodes_tag_appearances",
            ),
            path(
                "<path:object_id>/appearances/tag/",
                self.admin_site.admin_view(self.tag_view),
                name="episodes_appearance_tag",
            ),
            path(
                "<path:object_id>/appearances/link/",
                self.admin_site.admin_view(self.link_view),
                name="episodes_appearance_link",
            ),
            path(
                "<path:object_id>/appearances/untag/",
                self.admin_site.admin_view(self.untag_view),
                name="episodes_appearance_untag",
            ),
        ] + super().get_urls()

    def appearances_view(self, request, object_id):
        episode = get_object_or_404(Episode, pk=object_id)
        appearances = episode.appearances.select_related("candidate").all()
        tagged_names = {a.guest_name for a in appearances}
        suggestions = [name for name in episode.feed_guest_hosts if name not in tagged_names]
        live_candidates = Candidate.objects.filter(status=Candidate.Status.LIVE).order_by("stage_name")
        context = {
            **self.admin_site.each_context(request),
            "title": f"Appearances on {episode.episode_number}",
            "episode": episode,
            "appearances": appearances,
            "suggestions": suggestions,
            "form": TagAppearanceForm(),
            "live_candidates": live_candidates,
            "opts": self.model._meta,
        }
        return render(request, "admin/episodes/tag_appearances.html", context)

    @method_decorator(require_POST)
    def tag_view(self, request, object_id):
        episode = get_object_or_404(Episode, pk=object_id)
        form = TagAppearanceForm(request.POST)
        if not form.is_valid():
            self.message_user(request, "Name a guest host or pick a candidate.", level=messages.ERROR)
        else:
            try:
                appearance = tag_appearance(
                    episode,
                    request.user,
                    candidate=form.cleaned_data.get("candidate"),
                    guest_name=form.cleaned_data.get("guest_name") or "",
                    admin_note=form.cleaned_data.get("admin_note") or "",
                )
                self.message_user(request, f"Tagged {appearance.display_name}.", level=messages.SUCCESS)
            except TagError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        return HttpResponseRedirect(reverse("admin:episodes_tag_appearances", args=[episode.pk]))

    @method_decorator(require_POST)
    def link_view(self, request, object_id):
        episode = get_object_or_404(Episode, pk=object_id)
        appearance = get_object_or_404(Appearance, pk=request.POST.get("appearance_id"), episode=episode)
        candidate = get_object_or_404(Candidate, pk=request.POST.get("candidate_id"))
        try:
            link_candidate(appearance, candidate, request.user)
            self.message_user(
                request, f"Linked {appearance.guest_name} to {candidate.stage_name}.", level=messages.SUCCESS
            )
        except TagError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        return HttpResponseRedirect(reverse("admin:episodes_tag_appearances", args=[episode.pk]))

    @method_decorator(require_POST)
    def untag_view(self, request, object_id):
        episode = get_object_or_404(Episode, pk=object_id)
        appearance = get_object_or_404(Appearance, pk=request.POST.get("appearance_id"), episode=episode)
        name = appearance.display_name
        untag_appearance(appearance, request.user)
        self.message_user(request, f"Removed {name} from this episode.", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:episodes_tag_appearances", args=[episode.pk]))

    @method_decorator(require_POST)
    def resync_view(self, request):
        """Manual RSS re-sync (spec 4, Episode manager)."""
        run = sync_feed(settings.RSS_FEED_URL)
        if run.status == FeedSyncRun.Status.FAILED:
            self.message_user(request, f"Sync failed: {run.error}", level=messages.ERROR)
        else:
            self.message_user(
                request,
                f"Synced {run.items_seen} items: {run.episodes_created} created, "
                f"{run.episodes_updated} updated, {run.items_below_floor} below the episode floor, "
                f"{run.items_failed} unparseable.",
                level=messages.SUCCESS,
            )
        return HttpResponseRedirect(reverse("admin:episodes_episode_changelist"))


@admin.register(FeedSyncRun)
class FeedSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "status",
        "items_seen",
        "episodes_created",
        "episodes_updated",
        "items_below_floor",
        "items_failed",
    )
    list_filter = ("status",)
    readonly_fields = [f.name for f in FeedSyncRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
