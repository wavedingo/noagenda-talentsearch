from django.conf import settings
from django.core.mail import send_mail


def send_magic_link_email(to_email, raw_token):
    link_url = f"{settings.APP_URL}/auth/verify/{raw_token}/"
    send_mail(
        subject="Your No Agenda Talent Search sign-in link",
        message=f"Click to sign in (expires in 15 minutes): {link_url}",
        from_email=settings.MAIL_FROM,
        recipient_list=[to_email],
    )
