from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.request_magic_link, name="request_link"),
    path("signup/", views.request_magic_link, name="signup"),
]
