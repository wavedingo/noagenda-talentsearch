import django.utils.timezone
from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    """Phase 1 shipped the table without a slug. In practice no rows exist yet,
    but a migration that only works on an empty table isn't a migration."""
    Candidate = apps.get_model("candidates", "Candidate")
    taken = set()
    for candidate in Candidate.objects.all().order_by("pk"):
        base = slugify(candidate.stage_name)[:100] or "candidate"
        slug, suffix = base, 2
        while slug in taken:
            slug = f"{base}-{suffix}"[:110]
            suffix += 1
        taken.add(slug)
        candidate.slug = slug
        candidate.save(update_fields=["slug"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("candidates", "0001_initial")]

    operations = [
        # Added without the unique constraint so existing rows can be filled in
        # before it is applied.
        migrations.AddField(
            model_name="candidate",
            name="slug",
            field=models.CharField(blank=True, default="", max_length=110),
        ),
        migrations.RunPython(populate_slugs, noop_reverse),
        migrations.AlterField(
            model_name="candidate",
            name="slug",
            field=models.SlugField(max_length=110, unique=True),
        ),
        migrations.AddField(
            model_name="candidate",
            name="pending_stage_name",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="candidate",
            name="pending_bio",
            field=models.TextField(blank=True, max_length=1500),
        ),
        migrations.AddField(
            model_name="candidate",
            name="pending_photo_path",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="candidate",
            name="pending_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="candidate",
            name="rejection_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("audio_quality", "Audio quality"),
                    ("not_an_audition", "Not an audition demo"),
                    ("house_rules", "Breaks the house rules"),
                    ("impersonation", "Identity not verified"),
                    ("duplicate", "Duplicate submission"),
                    ("other", "Other"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="candidate",
            name="rejection_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="candidate",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name="candidate",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="demo",
            name="processing_state",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("ready", "Ready"),
                    ("failed", "Failed"),
                ],
                default="queued",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="demo",
            name="processing_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="demo",
            name="processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="demo",
            name="processing_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="demo",
            name="rejection_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("audio_quality", "Audio quality"),
                    ("not_an_audition", "Not an audition demo"),
                    ("house_rules", "Breaks the house rules"),
                    ("impersonation", "Identity not verified"),
                    ("duplicate", "Duplicate submission"),
                    ("other", "Other"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="demo",
            name="rejection_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="demo",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="demo",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name="demo",
            options={"ordering": ["-created_at"]},
        ),
    ]
