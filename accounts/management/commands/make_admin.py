from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from moderation.models import AdminAuditLog


class Command(BaseCommand):
    help = "Promote a user to the admin role, creating the account if it doesn't exist."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if not email:
            raise CommandError("email is required")

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"role": User.Role.ADMIN},
        )
        if not created:
            user.role = User.Role.ADMIN
            user.save(update_fields=["role"])
        else:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        AdminAuditLog.objects.create(
            admin_user=None,
            action="make_admin",
            target_type="user",
            target_id=user.id,
            metadata_json={"email": email, "created": created},
        )

        verb = "Created and promoted" if created else "Promoted"
        self.stdout.write(self.style.SUCCESS(f"{verb} {email} to admin."))
