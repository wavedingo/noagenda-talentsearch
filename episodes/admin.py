from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from .models import Episode, FeedSyncRun
from .sync import sync_feed


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("episode_number", "title_display", "published_at", "guest_hosts_display", "synced_at")
    search_fields = ("title_display", "title_raw", "guid")
    ordering = ("-published_at",)
    # Everything here is written by the sync job; hand-edits would be
    # overwritten on the next run.
    readonly_fields = [f.name for f in Episode._meta.fields]
    change_list_template = "admin/episodes/episode/change_list.html"

    @admin.display(description="Guest hosts (from feed)")
    def guest_hosts_display(self, obj):
        return ", ".join(obj.feed_guest_hosts) or "—"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [
            path(
                "resync/",
                self.admin_site.admin_view(self.resync_view),
                name="episodes_episode_resync",
            ),
        ] + super().get_urls()

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
