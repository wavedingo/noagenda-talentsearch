from django.contrib.auth.hashers import make_password
from django.shortcuts import render

from .emails import send_magic_link_email
from .forms import EmailForm
from .models import User
from .ratelimit import (
    email_link_requests_exceeded,
    ip_link_requests_exceeded,
    ip_signup_limit_exceeded,
)
from .tokens import create_magic_link
from .utils import get_client_ip


def request_magic_link(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        ip = get_client_ip(request)
        _maybe_send_magic_link(email, ip)
        return render(request, "accounts/link_sent.html")
    return render(request, "accounts/request_link.html", {"form": form})


def _maybe_send_magic_link(email, ip):
    if email_link_requests_exceeded(email) or ip_link_requests_exceeded(ip):
        return
    signup_limited = ip_signup_limit_exceeded(ip)
    user, created = User.objects.get_or_create(
        email=email, defaults={"signup_ip": ip, "password": make_password(None)}
    )
    if created and signup_limited:
        user.delete()
        return
    raw_token = create_magic_link(user, requested_ip=ip)
    send_magic_link_email(user.email, raw_token)
