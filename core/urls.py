import os

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
]

if os.environ.get("APP_ENV") != "production":
    urlpatterns += [path("__test-500__/", views._test_500, name="test_500")]
