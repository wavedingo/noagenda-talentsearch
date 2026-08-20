from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.request_magic_link, name="request_link"),
    path("signup/", views.request_magic_link, name="signup"),
    path("auth/verify/<str:token>/", views.verify_magic_link, name="verify"),
    path("auth/expired/", views.link_expired, name="link_expired"),
    path("logout/", views.logout_view, name="logout"),
]
