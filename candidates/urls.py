from django.urls import path

from . import views

app_name = "candidates"

urlpatterns = [
    path("candidates/", views.candidate_list, name="list"),
    path("candidates/<slug:slug>/", views.candidate_detail, name="detail"),
    path("candidates/<slug:slug>/report/", views.report_candidate, name="report"),
    path("audition/", views.audition, name="audition"),
    path("audition/demo/", views.upload_demo, name="upload_demo"),
    path("audition/withdraw/", views.withdraw, name="withdraw"),
    path("audition/reopen/", views.reopen, name="reopen"),
]
