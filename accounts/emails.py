from email.utils import make_msgid, parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

DEFAULT_MESSAGE_ID_DOMAIN = "noagendatalentsearch.com"


def _message_id_domain():
    """The domain to stamp into Message-ID, taken from the From address.

    Django otherwise derives Message-ID from socket.getfqdn(), which is the
    *host's* name — a Render container id in production, and a reverse-IPv6
    `.ip6.arpa` string on at least one dev machine. A Message-ID whose domain
    doesn't match the From domain is a well-known spam heuristic.

    Worth knowing before relying on this: Resend sends via Amazon SES, and SES
    replaces Message-ID with its own `@email.amazonses.com` value before the
    mail leaves. Raw headers from delivered mail confirm it. So on the current
    provider this header never reaches anyone, and it did not change the junk
    verdict at Yahoo or Outlook. It is kept because the Django default is
    wrong on its own terms and would start leaking the hostname the moment the
    provider changes — not because it is doing anything today.
    """
    _, address = parseaddr(settings.MAIL_FROM)
    _, separator, domain = address.rpartition("@")
    # rpartition returns the whole string as the tail when there is no "@",
    # so a bare "postmaster" would otherwise become the Message-ID domain.
    return domain if separator and domain else DEFAULT_MESSAGE_ID_DOMAIN


def sender_address():
    """The bare address, no display name -- what we ask people to allowlist."""
    _, address = parseaddr(settings.MAIL_FROM)
    return address


def send_magic_link_email(to_email, raw_token):
    link_url = f"{settings.APP_URL}/auth/verify/{raw_token}/"
    context = {"link_url": link_url, "app_url": settings.APP_URL}

    message = EmailMultiAlternatives(
        subject="Your No Agenda Talent Search sign-in link",
        body=render_to_string("accounts/email/magic_link.txt", context),
        from_email=settings.MAIL_FROM,
        to=[to_email],
        headers={
            "Message-ID": make_msgid(domain=_message_id_domain()),
            # Keeps out-of-office responders and ticket systems from replying
            # to a login link.
            "Auto-Submitted": "auto-generated",
        },
    )
    message.attach_alternative(
        render_to_string("accounts/email/magic_link.html", context), "text/html"
    )
    message.send()
