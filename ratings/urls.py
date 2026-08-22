from django.urls import path

from . import views

app_name = "ratings"

urlpatterns = [
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("rate/", views.rate, name="rate"),
]
