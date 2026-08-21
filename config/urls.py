from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("episodes.urls")),
    path("", include("candidates.urls")),
]

if settings.DEBUG and not settings.USE_R2:
    # Local-disk media, development only. In production uploads live in R2 and
    # are served from the media domain, never through Django.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
