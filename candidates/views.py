from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.settings_util import get_setting

from . import services
from .audio import DemoValidationError
from .forms import DemoForm, ProfileForm
from .images import PhotoValidationError
from .models import Candidate

CANDIDATES_PER_PAGE = 24

SORTS = {
    "newest": ("-approved_at", "-created_at"),
    "name": ("stage_name",),
}
DEFAULT_SORT = "newest"


def candidate_list(request):
    """Approved candidates only. Spec 6 lists a third sort, "top demos", which
    needs the Phase 4 scoring columns to mean anything — it lands with them."""
    sort = request.GET.get("sort", DEFAULT_SORT)
    if sort not in SORTS:
        sort = DEFAULT_SORT
    candidates = Candidate.objects.filter(status=Candidate.Status.LIVE).order_by(*SORTS[sort])
    page = Paginator(candidates, CANDIDATES_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "candidates/list.html",
        {"page_obj": page, "sort": sort, "auditions_open": get_setting("auditions_open")},
    )


def candidate_detail(request, slug):
    candidate = get_object_or_404(Candidate, slug=slug)
    is_owner = request.user.is_authenticated and candidate.user_id == request.user.pk
    if not candidate.is_public and not (is_owner or _is_moderator(request.user)):
        raise Http404("No such candidate")
    demo = candidate.live_demo
    return render(
        request,
        "candidates/detail.html",
        {"candidate": candidate, "demo": demo, "is_owner": is_owner},
    )


@login_required
def audition(request):
    candidate = Candidate.objects.filter(user=request.user).first()
    auditions_open = bool(get_setting("auditions_open"))

    if request.method == "POST":
        if not auditions_open and candidate is None:
            messages.error(request, "Auditions are closed at the moment.")
            return redirect("candidates:audition")
        form = _profile_form(candidate, request.POST, request.FILES)
        if form.is_valid():
            try:
                services.save_profile(
                    request.user,
                    form.cleaned_data["stage_name"],
                    form.cleaned_data["bio"],
                    photo_file=form.cleaned_data.get("photo") or None,
                    clear_photo=form.cleaned_data.get("clear_photo", False),
                )
            except PhotoValidationError as exc:
                form.add_error("photo", str(exc))
            else:
                messages.success(request, "Saved. A moderator will take a look shortly.")
                return redirect("candidates:audition")
    else:
        initial = {}
        if candidate is not None:
            initial = {
                "stage_name": candidate.pending_stage_name or candidate.stage_name,
                "bio": candidate.pending_bio if candidate.has_pending_edit else candidate.bio,
            }
        form = _profile_form(candidate, initial=initial)

    return render(
        request,
        "candidates/audition.html",
        {
            "form": form,
            "demo_form": DemoForm(),
            "candidate": candidate,
            "demo": candidate.current_demo if candidate else None,
            "auditions_open": auditions_open,
            "max_file_mb": get_setting("demo_max_file_mb"),
            "max_duration_min": int(get_setting("demo_max_duration_sec")) // 60,
        },
    )


@login_required
@require_POST
def upload_demo(request):
    candidate = Candidate.objects.filter(user=request.user).first()
    if candidate is None:
        messages.error(request, "Create your profile before uploading a demo.")
        return redirect("candidates:audition")
    if candidate.status == Candidate.Status.BANNED:
        raise Http404("No such candidate")

    form = DemoForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose an MP3 file to upload.")
        return redirect("candidates:audition")

    try:
        services.submit_demo(candidate, form.cleaned_data["demo"])
    except DemoValidationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Demo received. We're preparing it for playback, then a moderator will listen.",
        )
    return redirect("candidates:audition")


@login_required
@require_POST
def withdraw(request):
    candidate = _own_candidate(request)
    services.withdraw(candidate)
    messages.success(request, "Your profile is withdrawn and no longer public.")
    return redirect("candidates:audition")


@login_required
@require_POST
def reopen(request):
    candidate = _own_candidate(request)
    if candidate.status != Candidate.Status.WITHDRAWN:
        messages.error(request, "That profile isn't withdrawn.")
        return redirect("candidates:audition")
    services.reopen(candidate)
    messages.success(request, "Your profile is back in the queue for review.")
    return redirect("candidates:audition")


def _profile_form(candidate, *args, **kwargs):
    """Offering "remove my current photo" to someone with no photo is just a
    confusing checkbox."""
    form = ProfileForm(*args, **kwargs)
    has_photo = candidate is not None and (candidate.photo_path or candidate.pending_photo_path)
    if not has_photo:
        del form.fields["clear_photo"]
    return form


def _own_candidate(request):
    candidate = Candidate.objects.filter(user=request.user).first()
    if candidate is None:
        raise Http404("No audition profile")
    return candidate


def _is_moderator(user):
    return user.is_authenticated and user.role in (user.Role.MODERATOR, user.Role.ADMIN)
