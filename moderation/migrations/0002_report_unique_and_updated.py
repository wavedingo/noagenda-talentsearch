from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("moderation", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddConstraint(
            model_name="report",
            constraint=models.UniqueConstraint(
                fields=["reporter", "target_type", "target_id"],
                name="unique_report_per_user_target",
            ),
        ),
        migrations.AddIndex(
            model_name="report",
            index=models.Index(
                fields=["target_type", "target_id", "status"],
                name="report_target_status_idx",
            ),
        ),
    ]
