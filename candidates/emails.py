"""Moderation notices (spec 3.2: "rejects with an optional canned reason,
emailed to the candidate").

These land in the inbox of someone who put themselves forward during a grieving
period, so they read like a person wrote them (principle 3) and every rejection
says what happens next.
"""

from django.conf import settings
from django.core.mail import send_mail

from .models import REJECTION_MESSAGES, RejectionReason

SIGN_OFF = "\n\n— The No Agenda Talent Search team\nhello@noagendatalentsearch.com"


def _send(to_email, subject, body):
    send_mail(
        subject=subject,
        message=body + SIGN_OFF,
        from_email=settings.MAIL_FROM,
        recipient_list=[to_email],
    )


def _reason_text(reason, note):
    text = REJECTION_MESSAGES.get(reason, REJECTION_MESSAGES[RejectionReason.OTHER])
    return f"{text}\n\n{note}" if note else text


def send_candidate_approved(candidate):
    _send(
        candidate.user.email,
        "Your audition profile is live",
        f"Your profile is now live at {settings.APP_URL}/candidates/{candidate.slug}/.\n\n"
        "Thanks for putting yourself forward — it takes something to do that.",
    )


def send_candidate_rejected(candidate, reason, note=""):
    _send(
        candidate.user.email,
        "About your audition profile",
        "We've taken a look at your audition profile and can't publish it as it stands.\n\n"
        + _reason_text(reason, note),
    )


def send_profile_edit_rejected(candidate, reason, note=""):
    _send(
        candidate.user.email,
        "About your recent profile edit",
        "We couldn't publish your recent profile changes. Your existing profile is "
        "still live and unchanged.\n\n" + _reason_text(reason, note),
    )


def send_demo_approved(demo):
    _send(
        demo.candidate.user.email,
        "Your demo is live",
        f"Your demo is up at {settings.APP_URL}/candidates/{demo.candidate.slug}/ "
        "and producers can listen to it now.",
    )


def send_demo_rejected(demo, reason, note=""):
    _send(
        demo.candidate.user.email,
        "About your demo",
        "We've listened to your demo and can't publish this one.\n\n" + _reason_text(reason, note),
    )
