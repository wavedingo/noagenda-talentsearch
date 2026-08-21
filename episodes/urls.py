from django.urls import path

from . import views

app_name = "episodes"

urlpatterns = [
    path("episodes/", views.episode_list, name="list"),
    path("episodes/<int:number>/", views.episode_detail, name="detail"),
]
