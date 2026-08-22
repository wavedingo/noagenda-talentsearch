from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .emails import send_magic_link_email, sender_address
from .forms import AccountForm, EmailForm
from .models import User
from .ratelimit import (
    email_link_requests_exceeded,
    ip_link_requests_exceeded,
    ip_signup_limit_exceeded,
)
from .tokens import consume_magic_link, create_magic_link
from .utils import get_client_ip


def request_magic_link(request):
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        ip = get_client_ip(request)
        _maybe_send_magic_link(email, ip)
        return render(
            request, "accounts/link_sent.html", {"sender_address": sender_address()}
        )
    return render(request, "accounts/request_link.html", {"form": form})


def _maybe_send_magic_link(email, ip):
    if email_link_requests_exceeded(email) or ip_link_requests_exceeded(ip):
        return
    signup_limited = ip_signup_limit_exceeded(ip)
    # get_or_create (not UserManager.create_user()) so existing- and new-email
    # requests share one DB call, narrowing the timing side-channel between the
    # two cases. password=make_password(None) manually replicates
    # set_unusable_password() for that reason -- don't "simplify" this back to
    # create_user(), it reintroduces the timing asymmetry.
    with transaction.atomic():
        user, created = User.objects.get_or_create(
            email=email, defaults={"signup_ip": ip, "password": make_password(None)}
        )
        if created and signup_limited:
            user.delete()
            return
    raw_token = create_magic_link(user, requested_ip=ip)
    send_magic_link_email(user.email, raw_token)


def verify_magic_link(request, token):
    user = consume_magic_link(token)
    if user is None:
        return redirect("accounts:link_expired")
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    return redirect("core:home")


def link_expired(request):
    return request_magic_link(request) if request.method == "POST" else render(request, "accounts/link_expired.html")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:home")


@login_required
def account_view(request):
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            request.user.display_name = form.cleaned_data["display_name"]
            request.user.save(update_fields=["display_name"])
    else:
        form = AccountForm(initial={"display_name": request.user.display_name})
    return render(request, "accounts/account.html", {"form": form})


@login_required
@require_POST
def delete_account_view(request):
    user = request.user
    user.email = f"deleted-{user.id}@deleted.noagendatalentsearch.com"
    user.display_name = ""
    user.signup_ip = None
    user.deleted_at = timezone.now()
    user.save(update_fields=["email", "display_name", "signup_ip", "deleted_at"])
    logout(request)
    return redirect("core:home")
